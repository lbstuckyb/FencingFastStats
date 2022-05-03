import pandas as pd


df = pd.read_html('https://sistemainfo.fedesgrimacolombia.com/resultados?prueba=1925')
print(df)
