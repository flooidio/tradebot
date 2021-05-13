# fit an arima model
from pandas import read_csv
from statsmodels.tsa.arima.model import ARIMA
import numpy as np

# create a difference transform of the dataset
def difference(dataset):
    diff = list()
    for i in range(1, len(dataset)):
        value = dataset[i]-dataset[i-1]
        diff.append(value)
    return np.array(diff)

# load dataset
df = read_csv('BTC_USD_2021-05-05.csv', index_col=1, parse_dates=True, squeeze=True)
series = df['<CLOSE>']
X = difference(series.values)
# fit model
model = ARIMA(X, order=(2,1,2))
model_fit = model.fit()
# save model to file
model_fit.save('arima_model.pkl')
# save the differenced dataset
np.save('arima_data.npy', X)
# save the last observation
np.save('arima_obs.npy', [series.values[-1]])
