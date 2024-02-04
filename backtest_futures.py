
# Backtest code

# -- Import --

import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from binance.client import Client
from binance.enums import HistoricalKlinesType
import ta

import warnings
warnings.filterwarnings('ignore')

# -- Define Binance Client --
client = Client()


leverage = 1
wallet = 1000
makerFee = 0.0002
takerFee = 0.0006

# -- TP / SL parameters --
stopLossActivation = True
takeProfitActivation = True
SlPct = 0.025
TpPct = 0.05

# -- You can change the crypto pair, the start date and the time interval below --
pairName = 'ETHUSDT'
startDate = '2022-10-01'
timeInterval = '1h'

# -- Load all price data from binance API --
klinesT = client.get_historical_klines(pairName, timeInterval, startDate, 
                                       klines_type=HistoricalKlinesType.FUTURES)

# --- If you want to load data from other exchange (like Bybit), uncomment the line below --
#client = ccxt.bybit()
#klinesT = client.fetch_ohlcv(pairName, timeInterval, 
#                             since=client.parse8601('{0}T00:00:00'.format(startDate)))

# -- Define your dataset --
df = pd.DataFrame(np.array(klinesT)[:,:6], columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume'])
df['close'], df['high'], df['low'], df['open'] = pd.to_numeric(df['close']), pd.to_numeric(df['high']), pd.to_numeric(df['low']), pd.to_numeric(df['open'])
df = df.set_index(df['timestamp'])
df.index = pd.to_datetime(df.index, unit='ms')
del df['timestamp']
df
    
print("Data loaded 100%")

# -- Technical indicators --
df['RSI'] = ta.momentum.rsi(close=df['close'], window=14)
df['MA'] = ta.trend.sma_indicator(close=df['volume'], window=500)
df

plt.plot(df['RSI'])
plt.ylabel('RSI')
plt.show()
plt.plot(df['MA'])
plt.ylabel('MA 500')
plt.show()


print("Indicators loaded 100%")

# -- If you want to run your BackTest on a specific period, uncomment the line below --
#df = df['2022-11-01':'2023-03-05']

# -- Definition of dt, that will be the dataset to do your trades analyses --
dt = pd.DataFrame(columns=['date', 'position', 'reason', 'price', 'frais', 'wallet', 'drawBack'])


initialWallet = wallet
lastAth = wallet
stopLoss = 0
takeProfit = 500000
orderInProgress = ''
longIniPrice = 0
shortIniPrice = 0

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

# -- Iteration on all your price dataset (df) --
for index, row in df.iterrows():
    # -- If there is NO order in progress --
    if orderInProgress == '':
        # -- Check if you have to open a LONG --
        if openLongCondition(row):
            orderInProgress = 'LONG'
            longIniPrice = row['close']
            fee = wallet * leverage * takerFee
            wallet -= fee
            if stopLossActivation:
                stopLoss = longIniPrice - SlPct * longIniPrice
            if takeProfitActivation:
                takeProfit = longIniPrice + TpPct * longIniPrice
            # -- Add the trade to DT to analyse it later --
            myrow = {'date': index, 'position': 'Open Long', 'reason': 'Open Long Market', 'price': longIniPrice,
                     'frais': fee, 'wallet': wallet, 'drawBack': (wallet-lastAth)/lastAth}
            dt = dt.append(myrow, ignore_index=True)
        
        # -- Check if you have to open a SHORT --
        if openShortCondition(row):
            orderInProgress = 'SHORT'
            shortIniPrice = row['close'] 
            fee = wallet * leverage * takerFee
            wallet -= fee
            if stopLossActivation:
                stopLoss = shortIniPrice + SlPct * shortIniPrice
            if takeProfitActivation:
                takeProfit = shortIniPrice - TpPct * shortIniPrice
            # -- Add the trade to DT to analyse it later --
            myrow = {'date': index, 'position': 'Open Short', 'reason': 'Open Short Market', 'price': round(shortIniPrice, 2),
                     'frais': round(fee, 3), 'wallet':round(wallet+fee, 2), 'drawBack': round((wallet-lastAth)/lastAth, 3)}
            dt = dt.append(myrow, ignore_index=True) 
    # -- If there is an order in progress --
    if orderInProgress != '':
        closePosition = False
        # -- Check if there is a LONG order in progress --
        if orderInProgress == 'LONG':
            # -- Check Stop Loss --
            if row['low'] < stopLoss and stopLossActivation:
                orderInProgress = ''
                closePrice = stopLoss
                pr_change = (closePrice - longIniPrice) / longIniPrice
                position = 'Close Long'
                reason = 'Stop Loss Long'
                closePosition = True
            # -- Check Take Profit --
            elif row['high'] > takeProfit and takeProfitActivation:
                orderInProgress = ''
                closePrice = takeProfit
                pr_change = (closePrice - longIniPrice) / longIniPrice
                position = 'Close Long'
                reason = 'Take Profit Long'
                closePosition = True
            # -- Check if you have to close the LONG --
            elif closeLongCondition(row):
                orderInProgress = ''
                closePrice = row['close']
                pr_change = (closePrice - longIniPrice) / longIniPrice
                position = 'Close Long'
                reason = 'Close Market Long'
                closePosition = True
                
        # -- Check if there is a SHORT order in progress --
        elif orderInProgress == 'SHORT':
            # -- Check stop loss --
            if row['high'] > stopLoss and stopLossActivation :
                orderInProgress = ''
                closePrice = stopLoss
                #closePriceWithFee = closePrice + takerFee * closePrice
                pr_change = -(closePrice - shortIniPrice) / shortIniPrice
                position = 'Close Short'
                reason = 'Stop Loss Short'
                closePosition = True
            # -- Check take profit --
            elif row['low'] < takeProfit and takeProfitActivation:
                orderInProgress = ''
                closePrice = takeProfit
                pr_change = -(closePrice - shortIniPrice) / shortIniPrice
                position = 'Close Short'
                reason = 'Take Profit Short'
                closePosition = True
            # -- Check if you have to close the SHORT --
            elif closeShortCondition(row):
                orderInProgress = ''
                closePrice = row['close']
                pr_change = -(closePrice - shortIniPrice) / shortIniPrice
                position = 'Close Short'
                reason = 'Close Market Short'
                closePosition = True          
                
        if closePosition:
            fee = wallet * (1+pr_change) * leverage * takerFee
            wallet = wallet * (1+pr_change*leverage) - fee
            # -- Check if your wallet hit a new ATH to know the drawBack --
            if wallet > lastAth:
                lastAth = wallet
            # -- Add the trade to DT to analyse it later --
            myrow = {'date': index, 'position': position, 'reason': reason, 'price': round(closePrice, 2),
                     'frais': round(fee, 3), 'wallet': round(wallet, 2), 'drawBack': round((wallet-lastAth)/lastAth, 3),}
            dt = dt.append(myrow, ignore_index=True) 

# -- BackTest Analyses --
dt = dt.set_index(dt['date'])
dt.index = pd.to_datetime(dt.index)
dt['resultat%'] = dt['wallet'].pct_change()*100

dt['tradeIs'] = ''
dt.loc[dt['resultat%'] > 0, 'tradeIs'] = 'Good'
dt.loc[dt['resultat%'] < 0, 'tradeIs'] = 'Bad'

iniClose = df.iloc[0]['close']
lastClose = df.iloc[len(df)-1]['close']
holdPercentage = ((lastClose - iniClose)/iniClose)
algoPercentage = ((wallet - initialWallet)/initialWallet)

try:
    tradesPerformance = round(dt.loc[(dt['tradeIs'] == 'Good') | (dt['tradeIs'] == 'Bad'), 'resultat%'].sum()
            / dt.loc[(dt['tradeIs'] == 'Good') | (dt['tradeIs'] == 'Bad'), 'resultat%'].count(), 2)
except:
    tradesPerformance = 0
    print("/!\ There is no Good or Bad Trades in your BackTest, maybe a problem...")

try:
    totalGoodTrades = dt.groupby('tradeIs')['date'].nunique()['Good']
    averagePercentagePositivTrades = round(dt.loc[dt['tradeIs'] == 'Good', 'resultat%'].sum()
                                           / dt.loc[dt['tradeIs'] == 'Good', 'resultat%'].count(), 2)
except:
    totalGoodTrades = 0
    averagePercentagePositivTrades = 0
    print("/!\ There is no Good Trades in your BackTest, maybe a problem...")
try:
    totalBadTrades = dt.groupby('tradeIs')['date'].nunique()['Bad']
    averagePercentageNegativTrades = round(dt.loc[dt['tradeIs'] == 'Bad', 'resultat%'].sum()
                                           / dt.loc[dt['tradeIs'] == 'Bad', 'resultat%'].count(), 2)
except:
    totalBadTrades = 0
    averagePercentageNegativTrades = 0
    print("/!\ There is no Bad Trades in your BackTest, maybe a problem...")
    
totalTrades = totalGoodTrades + totalBadTrades
winRateRatio = (totalGoodTrades/totalTrades) * 100

print("BackTest finished, final wallet :", round(wallet,2), "$")

print("Starting balance :", initialWallet, "$")
print("Pair Symbol :",pairName,)
print("Period : [" + str(df.index[0]) + "] -> [" + str(df.index[len(df)-1]) + "]")

print("\n----- General Informations -----")
print("Final balance :", round(wallet, 2), "$")
print("Performance vs US dollar :", round(algoPercentage*100, 2), "%")
print("Buy and Hold Performance :", round(holdPercentage*100, 2), "%")
print("Win rate :", round(winRateRatio, 2), '%')
print("Worst Drawdown :", str(round(100*dt['drawBack'].min(), 2)), "%")
print("Total fees : ", round(dt['frais'].sum(), 2), "$")

print("\n----- Trades Informations -----")
print("Average trades performance :",tradesPerformance,"%")
print("Total trades on period :",totalTrades)
print("Number of positive trades :", totalGoodTrades)
print("Number of negative trades : ", totalBadTrades)
print("Average positive trades :", averagePercentagePositivTrades, "%")
print("Average negative trades :", averagePercentageNegativTrades, "%")

print("\n----- Trades Reasons -----")
reasons = dt['reason'].unique()
for r in reasons:
    print(r+" number :", dt.groupby('reason')['date'].nunique()[r])
del dt['date']
dt['wallet'].plot(figsize=(20, 10))

df.to_csv("candles.csv")
dt.to_csv("trades.csv")
