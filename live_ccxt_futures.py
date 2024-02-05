
# Live code for CEXs

# -- Import --
import numpy as np
import pandas as pd
from decimal import Decimal
import time
import ccxt
import ta

print(time.strftime("%y-%d-%m %H:%M:%S", time.gmtime()))

# Enter your own API-key and API-secret here
api_key = ''
api_secret = ''
client = ccxt.bybit({"apiKey": '', "secret": '', "options": {'defaultType': 'swap'}})

# -- Wallet -- 
initialWallet = 1000

# -- Hyper parameters --
leverage = 1
TpPct = 0.05
SlPct = 0.025

fiatSymbol = 'USDT'
coin = 'ETH'
pairSymbol = coin+'/'+fiatSymbol+':'+fiatSymbol
timeInterval = '1h'

# -- Load all price data from binance API --
klinesT = client.fetch_ohlcv(pairSymbol, timeInterval, limit=500)
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
    stepSize = 0.01  # figure to modified as function of the asset considered
    price = Decimal(str(price))
    return float(price - price % Decimal(str(stepSize)))

def get_balance(symbol):
    return round(client.fetchBalance()['total'][symbol], 2)
    
def get_position_balance_usd(symbol):
    try:
        position = client.fetchPosition(symbol)
        return round(float(position["initialMargin"]), 2)
    except:
        return 0

def get_position_balance(symbol):
    try:
        position = client.fetchPosition(symbol)
        return round(float(position["contracts"]) * float(position["contractSize"]), 2)
    except:
        return 

def positions(symbol):
    try:
        position = client.fetchPosition(symbol)
        if float(position['initialMargin']) > 0 and position['side']=="long":
            print("Long Position")
            return 'Long'
        elif float(position['initialMargin']) > 0 and position['side']=="short":
            print("Short Position")
            return 'Short'
        return ''
    except:
        return ''

wallet = get_balance(fiatSymbol)
usdtBalance = wallet
coinInUsdt = get_position_balance_usd(pairSymbol)
coinBalance = get_position_balance(pairSymbol)
usdtBalance -= coinInUsdt
print("Wallet:", round(wallet, 2), "$")
orderInProgress = positions(pairSymbol)

openOrders = client.fetch_open_orders(pairSymbol)
if len(openOrders) > 0 and orderInProgress == '':
    client.cancel_all_orders(pairSymbol)
actualPrice = df.iloc[-1]['close']

row = df.iloc[-2]

if orderInProgress == '':
    if openLongCondition(row):
        longQuantityInUsdt = usdtBalance * 0.9
        longAmount = convert_amount_to_precision(pairSymbol, longQuantityInUsdt*leverage/actualPrice)
        tpPrice = convert_price_to_precision(pairSymbol, actualPrice*(1+TpPct))
        slPrice = convert_price_to_precision(pairSymbol, actualPrice*(1-SlPct))
        try:
            client.create_order(pairSymbol, 'market', 'buy', longAmount, params={'leverage': leverage, 'takeProfitPrice': tpPrice, 'stopLossPrice': slPrice})
            print("Long", longAmount, coin, 'at', actualPrice)
        except:
            print("Unexpected error open long order !")
    elif openShortCondition(row): 
        shortQuantityInUsdt = usdtBalance * 0.9
        shortAmount = convert_amount_to_precision(pairSymbol, shortQuantityInUsdt*leverage/actualPrice)
        slPrice = convert_price_to_precision(pairSymbol, actualPrice*(1+SlPct))
        tpPrice = convert_price_to_precision(pairSymbol, actualPrice*(1-TpPct))
        try:
            client.create_order(pairSymbol, 'market', 'sell', longAmount, params={'leverage': leverage, 'takeProfitPrice': tpPrice, 'stopLossPrice': slPrice})
            print("Short", shortAmount, coin, 'at', actualPrice)
        except: 
            print("Unexpected error open short order !")  

if orderInProgress != '':
    if orderInProgress == 'Long' and closeLongCondition(row):   
        client.cancel_all_orders(pairSymbol)
        closeAmount = convert_amount_to_precision(pairSymbol, coinBalance*leverage*2)
        try:
            client.create_order(pairSymbol, "market", "sell", closeAmount, params={"reduceOnly": True})
            print("Close long position", round(coinBalance, 5), coin, 'at', actualPrice)
        except:
            print("Unexpected error close long order !")
        orderInProgress = ''
    elif orderInProgress == 'Short' and closeShortCondition(row):
        client.cancel_all_orders(pairSymbol)
        closeAmount = convert_amount_to_precision(pairSymbol, coinBalance*leverage*2)
        try:
            client.create_order(pairSymbol, "market", "buy", closeAmount, params={"reduceOnly": True})
            print("Close short position", round(coinBalance, 5), coin, 'at', actualPrice)
        except:
            print("Unexpected error close short order !")
        orderInProgress = ''

print("")
