
# Live code for Binance

# -- Import --
import numpy as np
import pandas as pd
from decimal import Decimal
import time
from binance.client import Client
from binance.enums import HistoricalKlinesType
import ta

print(time.strftime("%y-%d-%m %H:%M:%S", time.gmtime()))


client = Client(api_key='', api_secret='') # Enter your own API-key and API-secret here
#client = ccxt.bybit({"apiKey": '', "secret": '', "options": {'defaultType': 'future'}})

# -- Wallet -- 
initialWallet = 1000

# -- Hyper parameters --
leverage = 1
TpPct = 0.05
SlPct = 0.025

fiatSymbol = 'USDT'
coin = 'ETH'
pairSymbol = coin + fiatSymbol
timeInterval = '1h'

# -- Load all price data from binance API --
klinesT = client.get_historical_klines(pairSymbol, timeInterval, "30 day ago UTC", klines_type=HistoricalKlinesType.FUTURES)
df = pd.DataFrame(np.array(klinesT)[:,:6], columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume'])
df['close'], df['high'], df['low'], df['open'] = pd.to_numeric(df['close']), pd.to_numeric(df['high']), pd.to_numeric(df['low']), pd.to_numeric(df['open'])

df = df.set_index(df['timestamp'])
df.index = pd.to_datetime(df.index, unit='ms')
del df['timestamp']

# -- Technical indicators --
df['RSI'] = ta.momentum.rsi(close=df['close'], window=14)
df['MA'] = ta.trend.sma_indicator(close=df['close'], window=500)

# -- Condition to open Market LONG --
def openLongCondition(row):
    if (row['close'] > row['MA'] 
        and row['RSI'] < 30
    ):
        return True
    else:
        return False

# -- Condition to close Market LONG --
def closeLongCondition(row):
    if row['RSI'] > 70:
        return True
    else:
        return False

# -- Condition to open Market SHORT --
def openShortCondition(row):
    if (row['close'] < row['MA']
        and row['RSI'] > 70
    ):
        return True
    else:
        return False

# -- Condition to close Market SHORT --
def closeShortCondition(row):
    if row['RSI'] < 30:
        return True
    else:
        return False

def convert_amount_to_precision(symbol, amount):
    stepSize = 0.001  # figure to modified as function of the asset considered
    amount = Decimal(str(amount))
    return float(amount - amount % Decimal(str(stepSize)))

def convert_price_to_precision(symbol, price):
    stepSize = 0.01  # # figure to modified as function of the asset considered
    price = Decimal(str(price))
    return float(price - price % Decimal(str(stepSize)))

def get_balance(symbol):
    for liste in client.futures_account_balance():
        if liste['asset']==symbol:
            return float(liste['balance'])
    return 0
               
def get_position_balance(symbol):
    for liste in client.futures_account()['positions']:
        if liste['symbol']==symbol and float(liste['initialMargin'])>0:
            return float(liste['initialMargin']), float(liste['entryPrice'])
    return 0, 1

wallet = get_balance(fiatSymbol)
usdtBalance = wallet
coinInUsdt, entryPrice = get_position_balance(pairSymbol)
coinBalance = coinInUsdt / entryPrice
usdtBalance -= coinInUsdt
print("Wallet:", round(wallet, 2), "$")
orderInProgress = ''
for liste in client.futures_account()['positions']:
    if liste['symbol']==pairSymbol:
        if float(liste['initialMargin']) > 0.05*wallet and float(liste['notional']) > 0:
            orderInProgress = 'Long'
            print("Long Position")
        elif float(liste['initialMargin']) > 0.05*wallet and float(liste['notional']) < 0:
            orderInProgress = 'Short'
            print("Short Position")
 
openOrders = client.futures_get_open_orders(symbol=pairSymbol)
if len(openOrders) > 0 and orderInProgress == '':
    for openOrder in openOrders:
        client.futures_cancel_order(symbol=pairSymbol, orderId=openOrder['orderId'])
actualPrice = df.iloc[-1]['close']

row = df.iloc[-2]

if orderInProgress == '':
    if openLongCondition(row):
        longQuantityInUsdt = usdtBalance * 0.999
        longAmount = convert_amount_to_precision(pairSymbol, longQuantityInUsdt*leverage/actualPrice)
        try:
            long = client.futures_create_order(symbol=pairSymbol, side='BUY', type='MARKET', 
                                               quantity=longAmount, isolated=True, leverage=leverage)
            print("Long", longAmount, coin, 'at', actualPrice, long)
        except:
            print("Unexpected error open long order !")
        time.sleep(1)
        try:
            tpPrice = convert_price_to_precision(pairSymbol, actualPrice*(1+TpPct))
            client.futures_create_order(symbol=pairSymbol, side='SELL', type='TAKE_PROFIT_MARKET', 
                                        stopPrice=tpPrice, closePosition=True)
            slPrice = convert_price_to_precision(pairSymbol, actualPrice*(1-SlPct))
            client.futures_create_order(symbol=pairSymbol, side='SELL', type='STOP_MARKET', 
                                        stopPrice=slPrice, closePosition=True)
        except:
            print("Unexpected error TP/SL !")
    elif openShortCondition(row): 
        shortQuantityInUsdt = usdtBalance * 0.999
        shortAmount = convert_amount_to_precision(pairSymbol, shortQuantityInUsdt*leverage/actualPrice)
        try:
            short = client.futures_create_order(symbol=pairSymbol, side='SELL', type='MARKET', quantity=shortAmount, isolated=True, leverage=leverage)
            print("Short", shortAmount, coin, 'at', actualPrice, short)
        except: 
            print("Unexpected error open short order !")  
        time.sleep(1)
        try:
            tpPrice = convert_price_to_precision(pairSymbol, actualPrice*(1-TpPct))
            client.futures_create_order(symbol=pairSymbol, side='BUY', type='TAKE_PROFIT_MARKET', stopPrice=tpPrice, closePosition=True)
            slPrice = convert_price_to_precision(pairSymbol, actualPrice*(1+SlPct))
            client.futures_create_order(symbol=pairSymbol, side='BUY', type='STOP_MARKET', stopPrice=slPrice, closePosition=True)
        except:
            print("Unexpected error TP/SL !")

if orderInProgress != '':
    if orderInProgress == 'Long' and closeLongCondition(row):   
        for openOrder in openOrders:
            client.futures_cancel_order(symbol=pairSymbol, orderId=openOrder['orderId'])
        time.sleep(1)
        closeAmount = convert_amount_to_precision(pairSymbol, coinBalance*leverage*2)
        try:
            closeLong = client.futures_create_order(symbol=pairSymbol, side='SELL', type='MARKET', 
                                                    quantity=closeAmount, reduceOnly='true')
            print("Close long position", round(coinBalance, 5), coin, 'at', actualPrice, closeLong)
        except:
            print("Unexpected error close long order !")
        orderInProgress = ''
    elif orderInProgress == 'Short' and closeShortCondition(row):
        for openOrder in openOrders:
            client.futures_cancel_order(symbol=pairSymbol, orderId=openOrder['orderId'])
        time.sleep(1)
        closeAmount = convert_amount_to_precision(pairSymbol, coinBalance*leverage*2)
        try:
            closeShort = client.futures_create_order(symbol=pairSymbol, side='BUY', type='MARKET', 
                                                     quantity=closeAmount, reduceOnly='true')
            print("Close short position", round(coinBalance, 5), coin, 'at', actualPrice, closeShort)
        except:
            print("Unexpected error close short order !")
        orderInProgress = ''

print("")
