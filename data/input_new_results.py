import pandas as pd

from main import get_competition

h1 = pd.read_excel('./comp_results/incheo2may2022.xlsx', sheet_name='Hoja1', skiprows=1, header=1)  # poules
h2 = pd.read_excel('./comp_results/incheo2may2022.xlsx', sheet_name='Hoja2')  # resultados de la poule
h3 = pd.read_excel('./comp_results/incheo2may2022.xlsx', sheet_name='Hoja3')  # tablas preliminares
h4 = pd.read_excel('./comp_results/incheo2may2022.xlsx', sheet_name='Hoja4')  # tablas 256 a 16
h5 = pd.read_excel('./comp_results/incheo2may2022.xlsx', sheet_name='Hoja5')  # tablas T8 a final
h6 = pd.read_excel('./comp_results/incheo2may2022.xlsx', sheet_name='Hoja6')  # resultados finales
h7 = pd.read_excel('./comp_results/incheo2may2022.xlsx', sheet_name='Hoja7')  # info de la compe


current = get_competition(info=h7,
                          hj1=h1, hj2=h2, hj3=h3,
                          hj4=h4, hj5=h5, hj6=h6)

# if ist first competition to add


# if current['id'].value_counts().max() != 1:
#     print('Error! revisar ids')
# else:
#     current.to_csv('./new_results.csv')


# if its second or more competition to add


df = pd.read_csv('new_results.csv')
df.drop(columns=['Unnamed: 0'], inplace=True)

if current['id'].value_counts().max() != 1:
    print('Error! revisar ids')
else:
    final_df = pd.concat(objs=[df, current], ignore_index=True, sort=False)
    print(final_df.tail(1))
    final_df.to_csv('./data/new_results.csv')











#
# df = pd.read_csv('./results20apr2022.csv')
# print(df['date'])
# df.drop(columns=['Unnamed: 0'], inplace=True)
#
# print(df.tail(1))
#
# if current['id'].value_counts().max() != 1:
#     print('Error! revisar ids')
# else:
#     final_df = pd.concat(objs=[df, current], ignore_index=True, sort=False)
#     print(final_df.tail(1))
#     final_df.to_csv('./results20apr2022.csv')


# import pandas as pd
#
# df2 = pd.read_csv('https://raw.githubusercontent.com/lbstuckyb/FencingFastStats/master/updated_results.csv')
# print(df2)
#

#https://raw.githubusercontent.com/lbstuckyb/FencingFastSstats/master/results20apr2022.csv?token=GHSAT0AAAAAABTU4FQGOMNE2KCVBTA2PQZMYTCXP5Q
