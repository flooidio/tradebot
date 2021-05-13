#ACF plot of time series
from pandas import read_csv
from matplotlib import pyplot
from statsmodels.graphics.tsaplots import plot_acf, plot_pacf
import numpy as np

df = read_csv('BTC_USD_2021-05-05.csv', index_col=1, parse_dates=True, squeeze=True)
#series = df['<CLOSE>']
series = np.log(df['<CLOSE>']/df['<CLOSE>'].shift(1))

plot_acf(series)
plot_pacf(series)
pyplot.show()
