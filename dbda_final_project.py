# -*- coding: utf-8 -*-
"""DBDA Final Project.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1QP7kN1BudEzkx58gZmMirR70sx5lzXWI

# Importing necessary Packages and Libraries
"""

!pip install scikit-plot

# Commented out IPython magic to ensure Python compatibility.
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
import seaborn as sns
from scipy.stats import probplot, chi2_contingency, chi2
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OneHotEncoder, MinMaxScaler
from sklearn.metrics import ConfusionMatrixDisplay, classification_report, roc_curve, roc_auc_score,accuracy_score
from imblearn.over_sampling import SMOTE
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier, AdaBoostClassifier
from sklearn.naive_bayes import GaussianNB
from sklearn.neighbors import KNeighborsClassifier
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.inspection import permutation_importance
import scikitplot as skplt
from yellowbrick.model_selection import FeatureImportances
import scipy.stats as stats
import joblib
import os
# %matplotlib inline

!pip install pyspark

"""# Data Cleaning and Feature Engineering using Pyspark"""

from google.colab import drive
drive.mount('/content/drive')

#from pyspark import SparkContext,SparkConf
#conf = SparkConf().setAppName('CCAP').setMaster('local')
#sc = SparkContext(conf=conf)#entry point for programming with rdd

from pyspark.sql import SparkSession

spark = SparkSession.builder.appName("MyApp").getOrCreate() #entry point for programming with dataframes

cc_data_full_data=spark.read.load('/content/drive/MyDrive/DBDA Final Project/application_record.csv',format='csv',inferSchema=True,header=True)
cc_data_full_data.show(10)

cc_data_full_data.count()

credit_status = spark.read.load('/content/drive/MyDrive/DBDA Final Project/credit_record.csv',format='csv',inferSchema=True,header=True)
credit_status.show(10)

credit_status.count()

import pyspark.sql.functions as F

# groupby and aggregate to get the minimum MONTHS_BALANCE by ID
begin_month = credit_status.groupBy('ID').agg(F.abs(F.min('MONTHS_BALANCE')).alias('Account age'))

# rename the column to 'Account age'
begin_month = begin_month.withColumnRenamed('MONTHS_BALANCE', 'Account age')

# join the 'begin_month' DataFrame with 'cc_data_full_data' on 'ID'
cc_data_full_data = cc_data_full_data.join(begin_month, on='ID', how='left')

cc_data_full_data.show(10)

"""## Creating Target Column

###Classifying users as Risk or Not using STATUS if defaulted for 2 or more months

"""

from pyspark.sql.functions import when, count,lit

# Create a new column called dep_value and set its value to null
credit_status = credit_status.withColumn('dep_value', lit(None).cast('string'))

# Set dep_value to 'Yes' for all rows where STATUS is 2, 3, 4, or 5
credit_status = credit_status.withColumn('dep_value', when(credit_status.STATUS.isin([2, 3, 4, 5]), 'Yes').otherwise(credit_status.dep_value))

# Count the number of rows for each ID and create a new column called Target with values 'Yes' or 'No'
cpunt = credit_status.groupBy('ID').agg(count('dep_value').alias('dep_count'))
cpunt = cpunt.withColumn('Target', when(cpunt.dep_count > 0, 'Yes').otherwise('No'))

# Rename dep_value to Target and convert it to 1s and 0s
cc_data_full_data = cc_data_full_data.join(cpunt, on='ID', how='inner')
cc_data_full_data = cc_data_full_data.withColumnRenamed('dep_value', 'Target').withColumn('Target', when(cc_data_full_data.Target == 'Yes', 1).otherwise(0))
cc_data_full_data.select('Target').groupBy('Target').count().show()

cc_data_full_data=cc_data_full_data.drop('dep_count')

cc_data_full_data.show(10)

cc_data_full_data.write.format('csv').option('header', 'true').mode('overwrite').save('cc_full_data_prepared')

# Coalesce to a single partition
cc_data_full_data = cc_data_full_data.coalesce(1)

# Save as a single merged file
cc_data_full_data.write.format('csv') \
    .option('header', 'true') \
    .option('mergeSchema', 'true') \
    .mode('overwrite') \
    .save('cc_data_full_prepared')

#sc.stop()

"""# Data Preparation

## Using Pandas
"""

cc_data_full_data=pd.read_csv('/content/cc_data_full_prepared/part-00000-b087a501-e8b7-49f7-8a38-27a73848d219-c000.csv')

cc_data_full_data.head()

#Getting Age from DAYS_BIRTH column
cc_data_full_data['DAYS_BIRTH'].describe()

cc_data_full_data['DAYS_BIRTH']=(np.abs(cc_data_full_data['DAYS_BIRTH'])//365.25)
cc_data_full_data.rename(columns={'DAYS_BIRTH':'AGE'},inplace=True)
cc_data_full_data["AGE"].describe()

#Getting EMPLOYMENT LENGTH from DAYS EMPLOYED
cc_data_full_data['DAYS_EMPLOYED'][cc_data_full_data['DAYS_EMPLOYED'] >=0].value_counts() #corresponds to unemployed

cc_data_full_data['DAYS_EMPLOYED'][cc_data_full_data['DAYS_EMPLOYED'] >=0]=0 #replacing positive values with 0

cc_data_full_data['DAYS_EMPLOYED']=(np.abs(cc_data_full_data['DAYS_EMPLOYED'])//365.25)
cc_data_full_data.rename(columns={'DAYS_EMPLOYED':'EMPLOYMENT_LENGTH'},inplace=True)
cc_data_full_data['EMPLOYMENT_LENGTH'].describe()

cc_data_full_data.info()

cc_data_full_data.shape

(cc_data_full_data.isna().sum()/cc_data_full_data.shape[0])*100

new_data=cc_data_full_data.copy()

new_data['OCCUPATION_TYPE'].value_counts()

sns.countplot(new_data['OCCUPATION_TYPE'])
plt.xticks(rotation=90)

"""More than 30% of of values are missing in OCCUPATION TYPE column. From the above countplot we can see that Labourers is the most common occupation in our dataset. So we can impute the missing values with Laborers or we can just create another value as 'Others' and assign them to the missing values or the third option would be dropping the missing values."""

#Method 1: Imputing missing values with mode
new_data_imputed = new_data.copy()
new_data_imputed['OCCUPATION_TYPE']=new_data_imputed['OCCUPATION_TYPE'].replace(np.nan,'Laborers')
new_data_imputed.isna().sum()

#Method 2: Imputing missing values by creating new category
new_data_imputed_cat = new_data.copy()
new_data_imputed_cat['OCCUPATION_TYPE']=new_data_imputed_cat['OCCUPATION_TYPE'].replace(np.nan,'Other')
new_data_imputed_cat.isna().sum()

#Method 3: Dropping missing Values
new_data_drop_na = new_data.copy()
new_data_drop_na.dropna(inplace=True)
new_data_drop_na.isna().sum()

"""# EDA"""

def get_basic_info(df,feature):
  print('Description:\n{}'.format(df[feature].describe()))
  print('*'*50)
  print('Value Counts:\n{}'.format(df[feature].value_counts()))

"""## Univarite Analysis

### 1.Gender
"""

get_basic_info(new_data,'CODE_GENDER')

fig=plt.figure()
fig, ax = plt.subplots(figsize=(8,8))
# %1.2f%% display decimals in the pie chart with 2 decimal places
plt.pie(new_data['CODE_GENDER'].value_counts(),labels=new_data['CODE_GENDER'].value_counts().index, autopct='%1.2f%%', startangle=90, wedgeprops={'edgecolor' :'black'})
plt.title('Pie chart of Gender')
plt.legend(loc='best')
plt.axis('equal')

"""#### Inference:

Most of the applicants (67%) are Female.

### 2.Age
"""

new_data["AGE"].describe()

fig, ax = plt.subplots(figsize=(8,2))
sns.boxplot(new_data['AGE'])
plt.title('Age Distribution Boxplot')

fig, ax = plt.subplots(figsize=(9,5))
sns.histplot(new_data['AGE'],bins=20,kde=True)
plt.title('Age distribution Histogram')

"""####Inference:
The median Age of applicants is 43. Highest number of the applicants fall within the Age group of 30-40 Years

### 3.Education Type
"""

get_basic_info(new_data,'NAME_EDUCATION_TYPE')

sns.countplot(new_data['NAME_EDUCATION_TYPE'])
plt.xticks(rotation=90)

"""####Inference:
Highest number of applicants have completed Secondary Education

### 4.Family Status
"""

get_basic_info(new_data,'NAME_FAMILY_STATUS')

fig=plt.figure()
fig, ax = plt.subplots(figsize=(8,9))
# %1.2f%% display decimals in the pie chart with 2 decimal places
plt.pie(new_data['NAME_FAMILY_STATUS'].value_counts(),labels=new_data['NAME_FAMILY_STATUS'].value_counts().index, autopct='%1.2f%%', startangle=90, wedgeprops={'edgecolor' :'black'})
plt.title('Pie chart of Gender')
plt.legend(loc='best')
plt.axis('equal')

"""#### Inference:
Highest number of applicants are from Married people.

### 5. Family Member Count
"""

get_basic_info(new_data,'CNT_FAM_MEMBERS')

fig, ax = plt.subplots(figsize=(8,2))
sns.boxplot(new_data['CNT_FAM_MEMBERS'])
plt.title('Family Members Distribution Boxplot')

"""#### Inference:
Most applicants have 2 Family Members.

We also have 6 outliers, two of them are extreme with 15 and 20 Family Members

### 6.Children Count
"""

get_basic_info(new_data,'CNT_CHILDREN')

fig, ax = plt.subplots(figsize=(8,2))
sns.boxplot(new_data['CNT_CHILDREN'])
plt.title('Children Count Distribution Boxplot')

"""#### Inference:
Most of the applicants dont't have any children. This also explains why most applicants' Family Member count is 2.

We have 6 outliers in this case also. They might be the same which we found from Family Member Count

### 7.Housing Type
"""

get_basic_info(new_data,'NAME_HOUSING_TYPE')

sns.countplot(new_data['NAME_HOUSING_TYPE'])
plt.xticks(rotation=90)

"""#### Inference:
Almost every applicant lives in House/Apartment

### 8.Income
"""

get_basic_info(new_data,'AMT_INCOME_TOTAL')

fig, ax = plt.subplots(figsize=(2,8))
sns.boxplot(y=new_data['AMT_INCOME_TOTAL'])
plt.title('Income distribution(Boxplot)')
# suppress scientific notation
ax.get_yaxis().set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, p: format(int(x), ',')))

fig, ax = plt.subplots(figsize=(9,5))
sns.histplot(new_data['AMT_INCOME_TOTAL'],bins=20,kde=True)
plt.title('Income distribution Histogram')

"""#### Inference:
The average income is 186890 but this amount accounts for outliers. If we ignore the outlier most people make 157500

We have 3 applicants who makes more than 1000000

### 9.Employment Status
"""

get_basic_info(new_data,'NAME_INCOME_TYPE' )

sns.countplot(new_data['NAME_INCOME_TYPE'])
plt.xticks(rotation=45)

"""#### Inference:
Most applicants are employed

### 10.Car ownership
"""

get_basic_info(new_data,'FLAG_OWN_CAR')

sns.countplot(new_data['FLAG_OWN_CAR'])

"""#### Inference:
Higher number of applicants don't own a car

### 11.Property Ownership
"""

get_basic_info(new_data,'FLAG_OWN_REALTY')

sns.countplot(new_data['FLAG_OWN_REALTY'])

"""#### Inference:
Higher number of applicants own a property

### 12.Account Age
"""

get_basic_info(new_data,'Account age')

fig, ax = plt.subplots(figsize=(2,8))
sns.boxplot(y=new_data['Account age'])
plt.title('Account Age distribution(Boxplot)')

fig, ax = plt.subplots(figsize=(9,5))
sns.histplot(new_data['Account age'],bins=20,kde=True)
plt.title('Account Age distribution Histogram')

"""#### Inference:
Most accounts are 26 months old

Account age is not normally distributed, it is positively skewed

### 13.Contact Modes
"""

# Create a list of the column names
columns = ['FLAG_MOBIL', 'FLAG_WORK_PHONE', 'FLAG_PHONE','FLAG_EMAIL']
df_temp=pd.melt(new_data[columns])
sns.countplot(data=df_temp,x='variable',hue='value')

"""#### Inference:
  1.All applicants own a mobile phone.

  2.Most applicants don't own a work phone, phone and email.

### 14.Target
"""

get_basic_info(new_data,'Target')

sns.countplot(new_data['Target'])

"""#### Inference:
Most of the applicants are not considered as 'Risk'

There's a high imbalance in data which needs to be handled while training models

# Bivariate Analysis with Target

## 1. Numerical vs numerical features (Correlation & scatter plots)

### 1.1 Scatter plots
"""

new_data.info()

sns.pairplot(new_data[new_data['EMPLOYMENT_LENGTH'] > 0].drop(['ID','FLAG_MOBIL','FLAG_WORK_PHONE','FLAG_PHONE','FLAG_EMAIL','Target'],axis=1),corner=True)
plt.show()
# Interpretation:

# We can see a positive linear correlation between the family member and the children count. This makes sense, the more the children someone have, the larger the family member count. This is a multicollinearity problem. Meaning that the features are highly correlated. We will need to drop one of them.
# Another interesting trend is the Employment length and age. This also makes sense, the longer the employee has been working, the older they are.

"""### Interpretation:

1.We can see a positive linear correlation between the family member and the children count. This makes sense, the more the children someone have, the larger the family member count. This is a multicollinearity problem. Meaning that the features are highly correlated. We will need to drop one of them.

2.Another interesting trend is the Employment length and age. This also makes sense, the longer the employee has been working, the older they are.

###1.2 Family member count vs children count (numerical vs numerical feature comparison)
"""

sns.regplot(x='CNT_CHILDREN',y='CNT_FAM_MEMBERS',data=new_data,line_kws={'color': 'orange'})
plt.show()
# Interpretation:

# The more children a person has, the larger the family member count.

"""### Interpretation:

1. The more children a person has, the larger the family member count.

###1.3 Account age vs age (numerical vs numerical feature comparison)
"""

sns.jointplot(np.abs(new_data['Account age']),new_data['AGE'], kind="hex", height=12)
plt.yticks(np.arange(20,new_data['AGE'].max(), 5))
plt.xticks(np.arange(0, 65, 5))
plt.ylabel('AGE')
plt.show()
# Interpretation:

# Most of the applicants are between 20 and 45 years old and have an account that is less than 25 months old.

"""###Interpretation:

1. Most of the applicants are between 20 and 45 years old and have an account that is less than 25 months old.

###1.4 Employment length vs age (numerical vs numerical feature comparison)
"""

fig, ax = plt.subplots(figsize=(12,8))
sns.scatterplot(new_data['EMPLOYMENT_LENGTH'],new_data['AGE'],alpha=.05)
# # changing the frequency of the x-axis and y-axis labels
plt.xticks(np.arange(0,new_data['EMPLOYMENT_LENGTH'].max(), 2.5))
plt.yticks(np.arange(20, new_data['AGE'].max(), 5))
plt.show()
# Interpretation:

# This scatterplot shows that the age of the applicants is correlated with the length of the employment.
# The reason why it is shaped like a reversed triangle, it is because the age of the applicants increase with the length of the employment. You can't have an employment length > than the age.

"""###Interpretation:

1. This scatterplot shows that the age of the applicants is correlated with the length of the employment.
2. The reason why it is shaped like a reversed triangle, it is because the age of the applicants increase with the length of the employment. You can't have an employment length > than the age.

## 2 Correlation analysis
"""

# change the datatype of target feature to int
Target_int = new_data['Target'].astype('int32')

new_data.info()

# correlation analysis with heatmap, after dropping the has a mobile phone with the target feature as int
cc_train_copy_corr_no_mobile = pd.concat([new_data.drop(['FLAG_MOBIL','Target'], axis=1),Target_int],axis=1).corr()
# Get the lower triangle of the correlation matrix
# Generate a mask for the upper triangle
mask = np.zeros_like(cc_train_copy_corr_no_mobile, dtype='bool')
mask[np.triu_indices_from(mask)] = True
# Set up the matplotlib figure
fig, ax = plt.subplots(figsize=(18,10))
# seaborn heatmap
sns.heatmap(cc_train_copy_corr_no_mobile, annot=True, cmap='gnuplot',mask=mask, linewidths=.5)
# plot the heatmap
plt.show()

"""### Interpretation:

1.There is no feature that is correlated with the target feature

2.Family member count is highly correlated with children count as previously discussed

3.Age has some positive correlation with the family member count and children count. The older a person is, the most likely he/she will have a larger family.

4.Another positive correlation is having a phone and having a work phone.

5.The final positive correlation is between the age and work phone. The younger someone is the less likely he/she will have a work phone.

6.We also have a negative correlation between the employment length and the age as previously seen.

:##2. Numerical vs categorical features

###2.1 Age vs the rest of categorical features
"""

fig, axes = plt.subplots(4,2,figsize=(15,20),dpi=180)
fig.tight_layout(pad=5.0)
cat_features = ['CODE_GENDER', 'FLAG_OWN_CAR', 'FLAG_OWN_REALTY', 'EMPLOYMENT_LENGTH', 'NAME_EDUCATION_TYPE', 'NAME_FAMILY_STATUS', 'NAME_HOUSING_TYPE', 'OCCUPATION_TYPE']
for cat_ft_count, ax in enumerate(axes):
    for row_count in range(4):
        for feat_count in range(2):
            sns.boxplot(ax=axes[row_count,feat_count],x=new_data[cat_features[cat_ft_count]],y=np.abs(new_data['AGE'])/365.25)
            axes[row_count,feat_count].set_title(cat_features[cat_ft_count] + " vs age")
            plt.sca(axes[row_count,feat_count])
            plt.xticks(rotation=45,ha='right')
            plt.ylabel('AGE')
            cat_ft_count += 1
    break

"""###Interpretation:

1. Female applicants are older than their male counterpart.
2. Those who don't own a car tend to be older.
3. Those who own a property tend to be older than those who don't.
4. Of course, the pensioners are older that those who are working (We also see that some have pensioned at a young age, those are outliers).
5. It is also interesting to see that those who hold an academic degree are younger in general than the other groups.
6. Obviously, the widows tend to be much older. We also see some outliers in their 30's as well.
7. With no surprise, those who live with parent tend to be younger. We also see some outlier as well.
8. Lastly, who work as cleaning staff tend to be older while those who work in IT and to be younger.

###2.2 Income vs the rest of categorical features
"""

fig, axes = plt.subplots(4,2,figsize=(15,20),dpi=180)
fig.tight_layout(pad=5.0)

for cat_ft_count, ax in enumerate(axes):
    for row_count in range(4):
        for feat_count in range(2):
            sns.boxplot(ax=axes[row_count,feat_count],x=new_data[cat_features[cat_ft_count]],y=np.abs(new_data[new_data['EMPLOYMENT_LENGTH'] > 0]['EMPLOYMENT_LENGTH'])/365.25)
            axes[row_count,feat_count].set_title(cat_features[cat_ft_count] + " vs employment length")
            plt.sca(axes[row_count,feat_count])
            plt.ylabel('EMPLOYMENT_LENGTH')
            plt.xticks(rotation=45,ha='right')
            cat_ft_count += 1
    break

"""###Interpretation:

1. State employed applicant tend to have been employed longer than the rest.

2. Those who work in the medical field, have been employed longer than the rest.

##3 Categorical vs categorical features (Chi-square test)

Null hypothesis: the feature's categories have no effect on the target variable. Alternate hypothesis: one(or more) of the feature categories has a significant effect on the target variable.
"""

def chi_func(feature):
    # selection row with high risk
    high_risk_ft = new_data[new_data['Target'] == 1][feature]
    high_risk_ft_ct = pd.crosstab(index=high_risk_ft, columns=['Count']).rename_axis(None, axis=1)
    # drop the index feature name
    high_risk_ft_ct.index.name = None
    # observe values
    obs = high_risk_ft_ct
    print('Observed values:\n')
    print(obs)
    print('\n')
    # expected values
    print(obs.index)
    exp = pd.DataFrame([obs['Count'].sum()/len(obs)] * len(obs.index),columns=['Count'], index=obs.index)
    print('Expected values:\n')
    print(exp)
    print('\n')
    # chi-square test
    chi_squared_stat = (((obs-exp)**2)/exp).sum()
    print('Chi-square:\n')
    print(chi_squared_stat[0])
    print('\n')
    #critical value
    crit = stats.chi2.ppf(q = 0.95, df = len(obs) - 1)
    print('Critical value:\n')
    print(crit)
    print('\n')
    # p-value
    p_value = 1 - stats.chi2.cdf(x = chi_squared_stat, df = len(obs) - 1)
    print('P-value:\n')
    print(p_value)
    print('\n')
    if chi_squared_stat[0] >= crit:
        print('Reject the null hypothesis')
    elif chi_squared_stat[0] <= crit:
        print('Fail to reject the null hypothesis')

new_data.info()

cat_ft = ['CODE_GENDER', 'FLAG_OWN_CAR', 'FLAG_OWN_REALTY', 'EMPLOYMENT_LENGTH', 'NAME_EDUCATION_TYPE', 'NAME_FAMILY_STATUS', 'NAME_HOUSING_TYPE', 'OCCUPATION_TYPE']
for ft in cat_ft:
    print('\n\n**** {} ****\n'.format(ft))
    chi_func(ft)

"""2.5 Business findings from the EDA
*Typical profile of an applicant is: a Female in her early 40’s, married with a partner and no child. She has been employed for 5 years with a salary of 157500. She has completed her secondary education. She does not own a car but owns a property (a house/ apartment). Her account is 26 months old.*
*Age and income do not have any effects on the target variable*
*Those who are flagged as bad client, tend to have a shorter employment length and older accounts. They also constitute less than 2% of total applicants.*
*Most applicants are 20 to 45 years old and have an account that is 25 months old or less.*

# Data Preparation for Model Building
"""

new_data.head()

"""###Transformations to be done on each feature
**ID**:Drop the feature

**CODE_GENDER**:get dummies method

**Age**:Min-max scaling and Fix skewness


**NAME_FAMILY_STATUS**:get dummies method

**CNT_FAM_MEMBERS**:Fix outliers

**CNT_CHILDREN**:Drop feature

**Housing type**:get dummies method

**AMT_INCOME_TOTAL**:Remove outliers and Fix skewness and Min-max scaling

**OCCUPATION_TYPE**:One hot encoding and Impute missing values

**Employment status:**get dummies method

**NAME_EDUCATION_TYPE**:Ordinal encoding

**Employment length**:Remove outliers and Min-max scaling

**FLAG_OWN_CAR**:Change it numerical and get dummies method

**FLAG_OWN_REALTY**:Change it numerical and get dummies method

**FLAG_MOBIL**:Drop feature

**FLAG_WORK_PHONE**:get dummies method

**FLAG_PHONE**:get dummies method

**FLAG_EMAIL**:get dummies method

**Account age**: Drop feature

**Target**:Change the data type to numerical and balance the data
"""

new_data.info()

new_data.head()

new_data_dp = new_data.copy()

X_data = new_data_dp.drop('Target',axis=1)
Y_data = new_data_dp['Target']

X_data.to_csv('X_dataset.csv',index=False)

"""### Dropping Features"""

X_data.drop(['Account age','FLAG_MOBIL','CNT_CHILDREN','ID','OCCUPATION_TYPE',],axis=1,inplace=True)

"""### Encoding Categorical Features"""

cat_col = ['CODE_GENDER','NAME_FAMILY_STATUS','NAME_HOUSING_TYPE','NAME_INCOME_TYPE','NAME_EDUCATION_TYPE','FLAG_OWN_CAR','FLAG_OWN_REALTY','FLAG_WORK_PHONE','FLAG_PHONE','FLAG_EMAIL']

dummies=pd.get_dummies(X_data[cat_col],drop_first=True)

dummies.info()

X_data.drop(cat_col,axis=1,inplace=True)

X_data=pd.concat([dummies,X_data],axis=1)
X_data.head()

X_data.info()

"""### Handling Outliers"""

#Capping Outliers to 99 %ile
percentiles = X_data['CNT_FAM_MEMBERS'].quantile([0.05,0.99]).values
X_data['CNT_FAM_MEMBERS'][X_data['CNT_FAM_MEMBERS'] <= percentiles[0]] = percentiles[0]
X_data['CNT_FAM_MEMBERS'][X_data['CNT_FAM_MEMBERS'] >= percentiles[1]] = percentiles[1]

percentiles = X_data['AMT_INCOME_TOTAL'].quantile([0.05,0.99]).values
X_data['AMT_INCOME_TOTAL'][X_data['AMT_INCOME_TOTAL'] <= percentiles[0]] = percentiles[0]
X_data['AMT_INCOME_TOTAL'][X_data['AMT_INCOME_TOTAL'] >= percentiles[1]] = percentiles[1]

percentiles = X_data['EMPLOYMENT_LENGTH'].quantile([0.05,0.99]).values
X_data['EMPLOYMENT_LENGTH'][X_data['EMPLOYMENT_LENGTH'] <= percentiles[0]] = percentiles[0]
X_data['EMPLOYMENT_LENGTH'][X_data['EMPLOYMENT_LENGTH'] >= percentiles[1]] = percentiles[1]

"""### Feature Scaling

"""

scaler = MinMaxScaler()
num_cat=['AGE','AMT_INCOME_TOTAL','EMPLOYMENT_LENGTH','CNT_FAM_MEMBERS']

X_data[num_cat]=scaler.fit_transform(X_data[num_cat])

X_data.head()

X_data.info()

"""### Resampling using SMOTE"""

oversample = SMOTE(sampling_strategy='minority')
X_resampled, Y_resampled = oversample.fit_resample(X_data,Y_data)
print("Original dataset shape:", X_data.shape, Y_data.shape)
print("Resampled dataset shape:", X_resampled.shape, Y_resampled.shape)

X_resampled[X_resampled.index==69537]

pd.set_option('display.max_columns', None)
X_resampled.head()

"""# Model Selection and Evaluation

## Spliting data into Train and Test set
"""

X_train,X_test,Y_train,Y_test=train_test_split(X_resampled,Y_resampled,test_size=0.25,random_state=69)

"""## 1. Logistic Regression"""

logistic_regression=LogisticRegression(random_state=42,max_iter=1000)
logistic_model=logistic_regression.fit(X_train,Y_train)

Y_pred_lr=logistic_model.predict(X_test)

print("The accuracy of this model is: ",accuracy_score(Y_pred_lr,Y_test))

print(classification_report(Y_test,Y_pred_lr))

skplt.metrics.plot_roc(Y_test, logistic_model.predict_proba(X_test), title = 'ROC curve for Logistic Regression Model', cmap='cool',figsize=(8,6), text_fontsize='large')
plt.grid(visible=None)#remove the grid
plt.show()

fig, ax = plt.subplots(figsize=(8,8))
#plot confusion matrix
conf_matrix = ConfusionMatrixDisplay.from_predictions(Y_test, Y_pred_lr,ax=ax, cmap='Blues',values_format='d')
# remove the grid
plt.grid(visible=None)
# increase the font size of the x and y labels
plt.xlabel('Predicted label', fontsize=14)
plt.ylabel('True label', fontsize=14)
#give a title to the plot using the model name
plt.title('Confusion Matrix', fontsize=14)
#show the plot
plt.show()

plt.rcParams['xtick.labelsize'] = 12
plt.rcParams['ytick.labelsize'] = 12
# top 10 most predictive features
top_10_feat = FeatureImportances(logistic_model, relative=False, topn=10)
# top 10 least predictive features
bottom_10_feat = FeatureImportances(logistic_model, relative=False, topn=-10)
#change the figure size
plt.figure(figsize=(10, 4))
#change x label font size
plt.xlabel('xlabel', fontsize=14)
# Fit to get the feature importances
top_10_feat.fit(X_train, Y_train)
# show the plot
top_10_feat.show()
print('\n')
plt.figure(figsize=(10, 4))
plt.xlabel('xlabel', fontsize=14)
# Fit to get the feature importances
bottom_10_feat.fit(X_train, Y_train)
# show the plot
bottom_10_feat.show()

"""##2. Decision Tree Classifier"""

decision_tree=DecisionTreeClassifier(random_state=42)
decision_model=decision_tree.fit(X_train,Y_train)

Y_pred_dt=decision_model.predict(X_test)

print("The accuracy of this model is: ",accuracy_score(Y_pred_dt,Y_test))

print(classification_report(Y_test,Y_pred_dt))

skplt.metrics.plot_roc(Y_test, decision_model.predict_proba(X_test), title = 'ROC curve for Decision Tree Model', cmap='cool',figsize=(8,6), text_fontsize='large')
plt.grid(visible=None)#remove the grid
plt.show()

fig, ax = plt.subplots(figsize=(8,8))
#plot confusion matrix
conf_matrix = ConfusionMatrixDisplay.from_predictions(Y_test, Y_pred_dt,ax=ax, cmap='Blues',values_format='d')
# remove the grid
plt.grid(visible=None)
# increase the font size of the x and y labels
plt.xlabel('Predicted label', fontsize=14)
plt.ylabel('True label', fontsize=14)
#give a title to the plot using the model name
plt.title('Confusion Matrix', fontsize=14)
#show the plot
plt.show()

plt.rcParams['xtick.labelsize'] = 12
plt.rcParams['ytick.labelsize'] = 12
# top 10 most predictive features
top_10_feat = FeatureImportances(decision_model, relative=False, topn=10)
# top 10 least predictive features
bottom_10_feat = FeatureImportances(decision_model, relative=False, topn=-10)
#change the figure size
plt.figure(figsize=(10, 4))
#change x label font size
plt.xlabel('xlabel', fontsize=14)
# Fit to get the feature importances
top_10_feat.fit(X_train, Y_train)
# show the plot
top_10_feat.show()
print('\n')
plt.figure(figsize=(10, 4))
plt.xlabel('xlabel', fontsize=14)
# Fit to get the feature importances
bottom_10_feat.fit(X_train, Y_train)
# show the plot
bottom_10_feat.show()

"""##3. Random Forest Classifier"""

random_forest =RandomForestClassifier(random_state=42)
random_model=random_forest.fit(X_train,Y_train)

Y_pred_rf=random_model.predict(X_test)

print("The accuracy of this model is: ",accuracy_score(Y_pred_rf,Y_test))

print(classification_report(Y_test,Y_pred_rf))

skplt.metrics.plot_roc(Y_test, random_model.predict_proba(X_test), title = 'ROC curve for Random Forest Model', cmap='cool',figsize=(8,6), text_fontsize='large')
plt.grid(visible=None)#remove the grid
plt.show()

fig, ax = plt.subplots(figsize=(8,8))
#plot confusion matrix
conf_matrix = ConfusionMatrixDisplay.from_predictions(Y_test, Y_pred_rf,ax=ax, cmap='Blues',values_format='d')
# remove the grid
plt.grid(visible=None)
# increase the font size of the x and y labels
plt.xlabel('Predicted label', fontsize=14)
plt.ylabel('True label', fontsize=14)
#give a title to the plot using the model name
plt.title('Confusion Matrix', fontsize=14)
#show the plot
plt.show()

plt.rcParams['xtick.labelsize'] = 12
plt.rcParams['ytick.labelsize'] = 12
# top 10 most predictive features
top_10_feat = FeatureImportances(random_model, relative=False, topn=10)
# top 10 least predictive features
bottom_10_feat = FeatureImportances(random_model, relative=False, topn=-10)
#change the figure size
plt.figure(figsize=(10, 4))
#change x label font size
plt.xlabel('xlabel', fontsize=14)
# Fit to get the feature importances
top_10_feat.fit(X_train, Y_train)
# show the plot
top_10_feat.show()
print('\n')
plt.figure(figsize=(10, 4))
plt.xlabel('xlabel', fontsize=14)
# Fit to get the feature importances
bottom_10_feat.fit(X_train, Y_train)
# show the plot
bottom_10_feat.show()

"""##4. Gaussian Naive Bayes"""

gaussian_naive_bayes = GaussianNB()
gaussianNB_model = gaussian_naive_bayes.fit(X_train,Y_train)

Y_pred_gnb = gaussianNB_model.predict(X_test)

print("The accuracy of this model is: ",accuracy_score(Y_pred_gnb,Y_test))

print(classification_report(Y_test,Y_pred_gnb))

skplt.metrics.plot_roc(Y_test, gaussianNB_model.predict_proba(X_test), title = 'ROC curve for Gaussian Navie Bayes Model', cmap='cool',figsize=(8,6), text_fontsize='large')
plt.grid(visible=None)#remove the grid
plt.show()

fig, ax = plt.subplots(figsize=(8,8))
#plot confusion matrix
conf_matrix = ConfusionMatrixDisplay.from_predictions(Y_test, Y_pred_gnb,ax=ax, cmap='Blues',values_format='d')
# remove the grid
plt.grid(visible=None)
# increase the font size of the x and y labels
plt.xlabel('Predicted label', fontsize=14)
plt.ylabel('True label', fontsize=14)
#give a title to the plot using the model name
plt.title('Confusion Matrix', fontsize=14)
#show the plot
plt.show()

"""##5. K-Nearest Neighbour"""

k_nearest_neighbors =KNeighborsClassifier()
knn_model=k_nearest_neighbors.fit(X_train,Y_train)

Y_pred_knn=knn_model.predict(X_test)

print("The accuracy of this model is: ",accuracy_score(Y_pred_knn,Y_test))

print(classification_report(Y_test,Y_pred_knn))

skplt.metrics.plot_roc(Y_test, knn_model.predict_proba(X_test), title = 'ROC curve for K-Nearest Neighbors Model', cmap='cool',figsize=(8,6), text_fontsize='large')
plt.grid(visible=None)#remove the grid
plt.show()

fig, ax = plt.subplots(figsize=(8,8))
#plot confusion matrix
conf_matrix = ConfusionMatrixDisplay.from_predictions(Y_test, Y_pred_knn,ax=ax, cmap='Blues',values_format='d')
# remove the grid
plt.grid(visible=None)
# increase the font size of the x and y labels
plt.xlabel('Predicted label', fontsize=14)
plt.ylabel('True label', fontsize=14)
#give a title to the plot using the model name
plt.title('Confusion Matrix', fontsize=14)
#show the plot
plt.show()

"""##6.Gradient Boosting Classifier"""

gradient_boosting =GradientBoostingClassifier(random_state=42)
gradient_model = gradient_boosting.fit(X_train,Y_train)

Y_pred_gb = gradient_model.predict(X_test)

print("The accuracy of this model is: ",accuracy_score(Y_pred_gb,Y_test))

print(classification_report(Y_test,Y_pred_gb))

skplt.metrics.plot_roc(Y_test, gradient_model.predict_proba(X_test), title = 'ROC curve for GradientBoosting Classifier Model', cmap='cool',figsize=(8,6), text_fontsize='large')
plt.grid(visible=None)#remove the grid
plt.show()

fig, ax = plt.subplots(figsize=(8,8))
#plot confusion matrix
conf_matrix = ConfusionMatrixDisplay.from_predictions(Y_test, Y_pred_gb,ax=ax, cmap='Blues',values_format='d')
# remove the grid
plt.grid(visible=None)
# increase the font size of the x and y labels
plt.xlabel('Predicted label', fontsize=14)
plt.ylabel('True label', fontsize=14)
#give a title to the plot using the model name
plt.title('Confusion Matrix', fontsize=14)
#show the plot
plt.show()

plt.rcParams['xtick.labelsize'] = 12
plt.rcParams['ytick.labelsize'] = 12
# top 10 most predictive features
top_10_feat = FeatureImportances(gradient_model, relative=False, topn=10)
# top 10 least predictive features
bottom_10_feat = FeatureImportances(gradient_model, relative=False, topn=-10)
#change the figure size
plt.figure(figsize=(10, 4))
#change x label font size
plt.xlabel('xlabel', fontsize=14)
# Fit to get the feature importances
top_10_feat.fit(X_train, Y_train)
# show the plot
top_10_feat.show()
print('\n')
plt.figure(figsize=(10, 4))
plt.xlabel('xlabel', fontsize=14)
# Fit to get the feature importances
bottom_10_feat.fit(X_train, Y_train)
# show the plot
bottom_10_feat.show()

"""##7.Linear Discriminant Analysis"""

linear_discriminant_analysis = LinearDiscriminantAnalysis()
lda_model=linear_discriminant_analysis.fit(X_train,Y_train)

Y_pred_lda=lda_model.predict(X_test)

print("The accuracy of this model is: ",accuracy_score(Y_pred_lda,Y_test))
print('*'*100)
print(classification_report(Y_test,Y_pred_lda))
print('*'*100)
skplt.metrics.plot_roc(Y_test, lda_model.predict_proba(X_test), title = 'ROC curve for Linear Discriminant Analysis Model', cmap='cool',figsize=(8,6), text_fontsize='large')
plt.grid(visible=None)#remove the grid
plt.show()
print('*'*100)
fig, ax = plt.subplots(figsize=(8,8))
#plot confusion matrix
conf_matrix = ConfusionMatrixDisplay.from_predictions(Y_test, Y_pred_lda,ax=ax, cmap='Blues',values_format='d')
# remove the grid
plt.grid(visible=None)
# increase the font size of the x and y labels
plt.xlabel('Predicted label', fontsize=14)
plt.ylabel('True label', fontsize=14)
#give a title to the plot using the model name
plt.title('Confusion Matrix', fontsize=14)
#show the plot
plt.show()
print('*'*100)
plt.rcParams['xtick.labelsize'] = 12
plt.rcParams['ytick.labelsize'] = 12
# top 10 most predictive features
top_10_feat = FeatureImportances(lda_model, relative=False, topn=10)
# top 10 least predictive features
bottom_10_feat = FeatureImportances(lda_model, relative=False, topn=-10)
#change the figure size
plt.figure(figsize=(10, 4))
#change x label font size
plt.xlabel('xlabel', fontsize=14)
# Fit to get the feature importances
top_10_feat.fit(X_train, Y_train)
# show the plot
top_10_feat.show()
print('\n')
plt.figure(figsize=(10, 4))
plt.xlabel('xlabel', fontsize=14)
# Fit to get the feature importances
bottom_10_feat.fit(X_train, Y_train)
# show the plot
bottom_10_feat.show()

"""##8. AdaBoost"""

adaboost = AdaBoostClassifier(random_state=42)
ada_model=adaboost.fit(X_train,Y_train)

Y_pred_ada=ada_model.predict(X_test)

print("The accuracy of this model is: ",accuracy_score(Y_pred_ada,Y_test))
print('*'*100)
print(classification_report(Y_test,Y_pred_ada))
print('*'*100)
skplt.metrics.plot_roc(Y_test, ada_model.predict_proba(X_test), title = 'ROC curve for AdaBoost Model', cmap='cool',figsize=(8,6), text_fontsize='large')
plt.grid(visible=None)#remove the grid
plt.show()
print('*'*100)
fig, ax = plt.subplots(figsize=(8,8))
#plot confusion matrix
conf_matrix = ConfusionMatrixDisplay.from_predictions(Y_test, Y_pred_ada,ax=ax, cmap='Blues',values_format='d')
# remove the grid
plt.grid(visible=None)
# increase the font size of the x and y labels
plt.xlabel('Predicted label', fontsize=14)
plt.ylabel('True label', fontsize=14)
#give a title to the plot using the model name
plt.title('Confusion Matrix', fontsize=14)
#show the plot
plt.show()
print('*'*100)
plt.rcParams['xtick.labelsize'] = 12
plt.rcParams['ytick.labelsize'] = 12
# top 10 most predictive features
top_10_feat = FeatureImportances(ada_model, relative=False, topn=10)
# top 10 least predictive features
bottom_10_feat = FeatureImportances(ada_model, relative=False, topn=-10)
#change the figure size
plt.figure(figsize=(10, 4))
#change x label font size
plt.xlabel('xlabel', fontsize=14)
# Fit to get the feature importances
top_10_feat.fit(X_train, Y_train)
# show the plot
top_10_feat.show()
print('\n')
plt.figure(figsize=(10, 4))
plt.xlabel('xlabel', fontsize=14)
# Fit to get the feature importances
bottom_10_feat.fit(X_train, Y_train)
# show the plot
bottom_10_feat.show()

"""# Saving Model"""

+


/ 345678ertyufinal_model='final_model.sav'
joblib.dump(random_model,final_model)

