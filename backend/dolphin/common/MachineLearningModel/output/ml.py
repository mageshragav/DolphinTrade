import numpy as np
import pandas as pd
from scipy.stats import mode
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.svm import SVC
from sklearn.naive_bayes import GaussianNB
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, confusion_matrix

prediction = {
    'NEUTRAL': 1,
    'BUY': 2,
    'SELL': 3
}

def replace_momentum_uo(x):
    if x > 70:
        return prediction['BUY']
    elif x < 30:
        return prediction['SELL']
    else:
        return prediction['NEUTRAL']

def replace_momentum_rsi(x):
    if x > 70:
        return prediction['SELL']
    elif x < 30:
        return prediction['BUY']
    else:
        return prediction['NEUTRAL']

def replace_momentum_wr(x):
    if x in range(-20,0):
        return prediction['SELL']
    elif x in range(-100,-80):
        return prediction['BUY']
    else:
        return prediction['NEUTRAL']

def replace_trend_cci(x):
    if x > 100:
        return prediction['SELL']
    elif x < -100:
        return prediction['BUY']
    else:
        return prediction['NEUTRAL']

DATA_PATH = "common/MachineLearningModel/output/output_1.csv"
data = pd.read_csv(DATA_PATH).dropna(axis = 1)
data.replace(0.0,pd.NA,inplace=True)
data.dropna(inplace=True)
data.reset_index(drop=True,inplace=True)
# data['momentum_uo'] = data['momentum_uo'].apply(lambda x: replace_momentum_uo(x))
# data['momentum_wr'] = data['momentum_wr'].apply(lambda x: replace_momentum_wr(x))
# data['momentum_rsi'] = data['momentum_rsi'].apply(lambda x: replace_momentum_rsi(x))
# print(data.head())

X = data.iloc[:,7:-1]
y = data.iloc[:, -1]
# print(X.head())
# print(y.head())
X_train, X_test, y_train, y_test =train_test_split(
  X, y, test_size = 0.2, random_state = 24)


# Defining scoring metric for k-fold cross validation
def cv_scoring(estimator, X, y):
    return accuracy_score(y, estimator.predict(X))
 
# Initializing Models
# models = {
#     "SVC":SVC(),
#     "Random Forest":RandomForestClassifier(random_state=18)
# }
 
# # Producing cross validation score for the models
# for model_name in models:
#     model = models[model_name]
#     scores = cross_val_score(model, X, y, cv = 10, 
#                              n_jobs = -1, 
#                              scoring = cv_scoring)
#     print("=="*30)
#     print(model_name)
#     print(f"Scores: {scores}")
#     print(f"Mean Score: {np.mean(scores)}")

svm_model = SVC()
svm_model.fit(X_train, y_train)
preds = svm_model.predict(X_test)
 
print(f"Accuracy on train data by SVM Classifier\
: {accuracy_score(y_train, svm_model.predict(X_train))*100}")
 
print(f"Accuracy on test data by SVM Classifier\
: {accuracy_score(y_test, preds)*100}")
cf_matrix = confusion_matrix(y_test, preds)
plt.figure(figsize=(12,8))
sns.heatmap(cf_matrix, annot=True)
plt.title("Confusion Matrix for SVM Classifier on Test Data")
plt.show()
# Checking whether the dataset is balanced or not
# data_counts = data["prognosis"].value_counts()

# temp_df = pd.DataFrame({
#     "Disease": disease_counts.index,
#     "Counts": disease_counts.values
# })