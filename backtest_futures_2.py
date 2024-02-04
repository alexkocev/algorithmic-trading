
# Backtest code

# -- Import --
import pandas as pd
from binance.client import Client
import ta
import numpy as np
from binance.enums import HistoricalKlinesType
import datetime
import warnings
warnings.filterwarnings('ignore')

# -- Define Binance Client --
client = Client()


leverage = 1
wallet = 1000
makerFee = 0.0002
takerFee = 0.0004
maxDrawdown = -0.5

# -- TP / SL parameters --
stopLossActivation = False
takeProfitActivation = False
SlPct = 0.025
TpPct = 0.05

# -- You can change the crypto pair ,the start date and the time interval below --
pairName = "ETHUSDT"
startDate = "01 october 2022"
timeInterval = '15m'

# -- Load all price data from binance API --
klinesT = client.get_historical_klines(pairName, timeInterval, startDate, klines_type=HistoricalKlinesType.FUTURES)
# --- Load data from other exchange (like Bybit) --
#client = ccxt.bybit()
#klinesT = client.fetch_ohlcv(pairName, timeInterval, since=client.parse8601('{0}T00:00:00'.format(startDate)))

# -- Define your dataset --
df = pd.DataFrame(np.array(klinesT)[:,:6], columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume'])
df['close'], df['high'], df['low'], df['open'] = pd.to_numeric(df['close']), pd.to_numeric(df['high']), pd.to_numeric(df['low']), pd.to_numeric(df['open'])
    
# -- Set the date to index --
df = df.set_index(df['timestamp'])
df.index = pd.to_datetime(df.index, unit='ms')
del df['timestamp']
    
print("Data loaded 100%")

# -- Technical indicators --
df['RSI'] = ta.momentum.rsi(close=df['close'], window=14)
df['MA'] = ta.trend.sma_indicator(close=df['close'], window=500)

print("Indicators loaded 100%")


# -- If you want to run your BackTest on a specific period, uncomment the line below --
#df = df['2022-11-01':'2023-03-05']

# -- Definition of dt, that will be the dataset to do your trades analyses --
dt = pd.DataFrame(columns=['date', 'position', 'reason',
                           'price', 'frais', 'wallet', 'drawBack'])

initialWallet = wallet
lastAth = wallet
previousRow = df.iloc[0]
stopLoss = 0
takeProfit = 500000
orderInProgress = ''
longIniPrice = 0
shortIniPrice = 0
lastPosition = 'short'
lastPrChange = 0

# -- Condition to open Market LONG --
def openLongCondition(row, previousRow):
    if (row['close'] > row['MA'] 
        and row['RSI'] < 30 and previousRow['RSI'] > 30
    ):
        return True
    else:
        return False

# -- Condition to close Market LONG --
def closeLongCondition(row, previousRow):
    if row['RSI'] > 70 and previousRow['RSI'] < 70:
        return True
    else:
        return False

# -- Condition to open Market SHORT --
def openShortCondition(row, previousRow):
    if (row['close'] < row['MA']
        and row['RSI'] > 70 and previousRow['RSI'] < 70
    ):
        return True
    else:
        return False

# -- Condition to close Market SHORT --
def closeShortCondition(row, previousRow):
    if row['RSI'] < 30  and previousRow['RSI'] > 30:
        return True
    else:
        return False

# -- Iteration on all your price dataset (df) --
for index, row in df.iterrows():
    stopTrades = (wallet-initialWallet)/initialWallet < maxDrawdown
    if stopTrades:
        print("no trading")
    if wallet > initialWallet:
        algoBenefit = ((wallet - initialWallet)/initialWallet)
        proportionTrading = (initialWallet*(1+algoBenefit*0.5))/wallet
    else:
        proportionTrading = 1
    hour = int(str(index)[-8:-6])
    year, month, day = int(str(index)[0:4]), int(str(index)[5:7]), int(str(index)[8:10])
    weekDay = datetime.date(year, month, day).weekday()
    conditionDate = weekDay < 5
    # -- If there is NO order in progress --
    if orderInProgress == '' and not stopTrades and conditionDate:
        # -- Check if you have to open a LONG --
        if openLongCondition(row, previousRow) and not (lastPosition=='long' and lastPrChange<0):
            orderInProgress = 'LONG'
            longIniPrice = row['close']
            fee = wallet * proportionTrading * leverage * takerFee
            wallet -= fee
            if stopLossActivation:
                stopLoss = longIniPrice - SlPct * longIniPrice
            if takeProfitActivation:
                takeProfit = longIniPrice + TpPct * longIniPrice
            # -- Add the trade to DT to analyse it later --
            myrow = {'date': index, 'position': 'Open Long', 'reason': 'Open Long Market', 'price': round(longIniPrice, 2),
                     'frais': round(fee, 3), 'wallet': round(wallet+fee, 2), 'drawBack': round((wallet-lastAth)/lastAth, 3)}
            dt = dt.append(myrow, ignore_index=True)
        
        # -- Check if you have to open a SHORT --
        if openShortCondition(row, previousRow) and not (lastPosition=='short' and lastPrChange<0):
            orderInProgress = 'SHORT'
            shortIniPrice = row['close'] 
            fee = wallet * proportionTrading * leverage * takerFee
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
            elif closeLongCondition(row, previousRow):
                orderInProgress = ''
                closePrice = row['close']
                pr_change = (closePrice - longIniPrice) / longIniPrice
                position = 'Close Long'
                reason = 'Close Market Long'
                closePosition = True
            else:
                stopLossTrail = row['close'] - SlPct * row['close']
                if stopLossTrail < row['close'] and stopLossTrail > stopLoss:
                    stopLoss = stopLossTrail
                
        # -- Check if there is a SHORT order in progress --
        elif orderInProgress == 'SHORT':
            # -- Check stop loss --
            if row['high'] > stopLoss and stopLossActivation :
                orderInProgress = ''
                closePrice = stopLoss
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
            elif closeShortCondition(row, previousRow):
                orderInProgress = ''
                closePrice = row['close']
                pr_change = -(closePrice - shortIniPrice) / shortIniPrice
                position = 'Close Short'
                reason = 'Close Market Short'
                closePosition = True
            else:
                stopLossTrail = row['close'] + SlPct * row['close']
                if stopLossTrail > row['close'] and stopLossTrail < stopLoss:
                    stopLoss = stopLossTrail            
                
        if closePosition:
            fee = wallet * proportionTrading * (1+pr_change) * leverage * takerFee
            wallet = wallet * (1-proportionTrading) + wallet * proportionTrading * (1+pr_change*leverage) - fee
            # -- Check if your wallet hit a new ATH to know the drawBack --
            if wallet > lastAth:
                lastAth = wallet
            # -- Add the trade to DT to analyse it later --
            myrow = {'date': index, 'position': position, 'reason': reason, 'price': round(closePrice, 2),
                     'frais': round(fee, 3), 'wallet': round(wallet, 2), 'drawBack': round((wallet-lastAth)/lastAth, 3),}
            dt = dt.append(myrow, ignore_index=True) 
            if dt.iloc[-1]['position'][-1] == 't':
                lastPosition = 'short'
                lastPrChange = pr_change
            elif dt.iloc[-1]['position'][-1] == 'g':
                lastPosition = 'long'
                lastPrChange = pr_change
                
    previousRow = row

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
worstDrawdown = 100*dt['drawBack'].min()

tradesPerformance = round(dt.loc[(dt['tradeIs'] == 'Good') | (dt['tradeIs'] == 'Bad'), 'resultat%'].sum()
            / dt.loc[(dt['tradeIs'] == 'Good') | (dt['tradeIs'] == 'Bad'), 'resultat%'].count(), 2)
totalGoodTrades = dt.groupby('tradeIs')['date'].nunique()['Good']
averagePercentagePositivTrades = round(dt.loc[dt['tradeIs'] == 'Good', 'resultat%'].sum()
                                           / dt.loc[dt['tradeIs'] == 'Good', 'resultat%'].count(), 2)
totalBadTrades = dt.groupby('tradeIs')['date'].nunique()['Bad']
averagePercentageNegativTrades = round(dt.loc[dt['tradeIs'] == 'Bad', 'resultat%'].sum()
                                           / dt.loc[dt['tradeIs'] == 'Bad', 'resultat%'].count(), 2)
totalTrades = totalGoodTrades + totalBadTrades
winRateRatio = (totalGoodTrades/totalTrades) * 100

print("BackTest finished, final wallet :", round(wallet,2), "$")

print("Pair Symbol :",pairName,)
print("Period : [" + str(df.index[0]) + "] -> [" +
      str(df.index[len(df)-1]) + "]")
print("Starting balance :", initialWallet, "$")

print("\n----- General Informations -----")
print("Final balance :", round(wallet, 2), "$")
print("Performance vs US dollar :", round(algoPercentage*100, 2), "%")
print("Win rate :", round(winRateRatio, 2), '%')
print("Worst Drawdown :", round(worstDrawdown, 2), "%")
print("Buy and Hold Performence :", round(holdPercentage*100, 2), "%")
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

#df.to_csv("candles.csv")
#dt.to_csv("trades.csv")
