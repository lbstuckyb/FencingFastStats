import dash
import dash_core_components as dcc
import dash_html_components as html
import plotly.graph_objs as go
import pandas as pd
import numpy as np
from dash.dependencies import Input, Output, State
import datetime as dt
import dash_auth
import dash_table
import requests
from io import StringIO

# USERNAME_PASSWORD_PAIRS = [['fce','fce']]

app = dash.Dash()
app.config['suppress_callback_exceptions'] = True
server = app.server

orig_url1 = 'https://drive.google.com/file/d/1Y9eel4Ii_gP4B2kYWGR2AdtmwdaWUCIE/view?usp=sharing'
file_id1 = orig_url1.split('/')[-2]
dwn_url1 = 'https://drive.google.com/uc?export=download&id=' + file_id1
url1 = requests.get(dwn_url1).text
csv_raw1 = StringIO(url1)
rank = pd.read_csv(csv_raw1)

# international Data
csv_raw2 = 'https://raw.githubusercontent.com/lbstuckyb/FencingFastStats/master/final_results/results27may2022.csv'
df = pd.read_csv(csv_raw2)

df.dropna(subset=["date"], inplace=True)
df.drop(columns=['Unnamed: 0'], inplace=True)
df['date'] = df['date'].astype(str)
df['date'] = df['date'].apply(lambda x: x.split(' ')[0])

df['date'] = df['date'].apply(lambda x: dt.datetime.strptime(x, '%Y-%m-%d'))

# Colombian Data
csv_raw3 = 'https://raw.githubusercontent.com/lbstuckyb/FencingFastStats/master/data/COL.csv'
col_df = pd.read_csv(csv_raw3)
col_df.drop(columns=['Unnamed: 0'], inplace=True)
col_df['date'] = col_df['date'].astype(str)
col_df['date'] = col_df['date'].apply(lambda x: x.split(' ')[0])
col_df['date'] = col_df['date'].apply(lambda x: dt.datetime.strptime(x, '%Y-%m-%d'))
# col_df.drop_duplicates(subset=['id', 'comp', 'date', 'category'],
#                        keep='first', inplace=True, ignore_index=True)

features = [{'label': 'Posición final', 'value': 'POS'},
            # {'label': 'Ingreso a cuadro de 96', 'value': 'T96+'},
            # {'label': 'Ingreso a cuadro de 64', 'value': 'T64+'},
            # {'label': 'Avanzar la poule', 'value': 'Q'},
            {'label': 'Indicador de la poule', 'value': 'PIND'},
            {'label': 'Victorias en la poule', 'value': 'PVICT'},
            {'label': 'Toques recibidos en poule', 'value': 'PTR'},
            {'label': 'Toques dados en poule', 'value': 'PTD'},
            {'label': 'Diferencial toques en poule', 'value': 'PT-DIFF'},
            {'label': 'Promedio toques recibidos combate de poule', 'value': 'PMTR'},
            {'label': 'Promedio toques dados combate de poule', 'value': 'PMTD'},
            {'label': 'Diferencial promedio toques en combates de poule', 'value': 'PMT-DIFF'},
            {'label': 'Promedio toques recibidos en cuadro', 'value': 'TTR'},
            {'label': 'Promedio toques dados en cuadro', 'value': 'TTD'},
            {'label': 'Diferencia promedio toques en combate de cuadro', 'value': 'TMT-DIFF'},
            # {'label': 'Promedio de victorias en cuadro', 'value': 'TMVAVG'}
            ]

# auth = dash_auth.BasicAuth(app,USERNAME_PASSWORD_PAIRS)

app.layout = html.Div([
    html.H1('FCE STATS', style={'font-size': 60, 'text-align': 'center',
                                'font-style': 'bold', 'font-family': 'verdana'}),
    # html.H2('Seguimiento Estadístico', style={'font-size': 30, 'text-align': 'center'}),
    html.Div([
        dcc.Tabs(id="tabs", value='tab-2', children=[
            # dcc.Tab(label='Internacional', value='tab-1'),
            dcc.Tab(label='Competencias Nacionales', value='tab-2'),
            # dcc.Tab(label='Análisis de Variables', value='tab-3'),
            dcc.Tab(label='Información de Variables', value='tab-4')

        ]),
        html.Div(id='tabs-content')
    ], style={'padding': 30}),
    html.H3('Powered by Lucas Stucky - LBSB', style={'font-size': 10, 'text-align': 'center', 'font-style': 'italic'})
], style={'font-family': 'verdana', 'color': 'rgb(0, 72, 132)'})


# tabs
@app.callback(Output('tabs-content', 'children'),
              [Input('tabs', 'value')])
def render_content(tab):
    if tab == 'tab-1':
        return html.Div([
            html.H3('Rendimiento Individual del Atleta'),
            html.Div([
                html.Div([
                    dcc.Dropdown(id='indres_esg-picker',
                                 options=[{'label': i, 'value': i} for i in df['name'].unique()],
                                 multi=True,
                                 style={'width': '100%'},
                                 value=[]),
                    html.H4(id='fencer_name'),
                    html.H4(id='fencer_country'),
                    html.H4(id='fencer_weapons'),
                    html.H4(id='fencer_hand'),
                    html.H4(id='fencer_rank'),
                    html.Div(id='tabla-individual'),
                    html.Div([
                        html.Div([html.Div([
                            html.Div([html.H4('Variables de Comparación', style={'justify-content': 'center',
                                                                                 'display': 'flex'}),
                                      dcc.Dropdown(id='yaxis_indres',
                                                   options=features,
                                                   value='POS')
                                      ], style={'width': '40%'}),
                            html.Div([html.Div([
                                html.H4('Periodos de tiempo', style={'justify-content': 'center',
                                                                     'display': 'flex'}),
                                html.Div([dcc.DatePickerRange(id='custom_date_range',
                                                              month_format='MMMM Y',
                                                              end_date_placeholder_text='MMMM Y',
                                                              start_date_placeholder_text='MMMM Y',
                                                              min_date_allowed=df['date'].min(),
                                                              clearable=True, )

                                          ], style={'justify-content': 'center', 'display': 'flex',
                                                    'vertical-align': 'middle', 'width': '100%',
                                                    'font-size': 13}),
                                html.Div([dcc.RadioItems(id='timeframes',
                                                         options=[
                                                             {'label': 'Todo', 'value': pd.Timestamp(
                                                                 dt.date.today() - dt.timedelta(days=12 * 365))},
                                                             {'label': '2 Años', 'value': pd.Timestamp(
                                                                 dt.date.today() - dt.timedelta(days=2 * 365))},
                                                             {'label': '1 Año', 'value': pd.Timestamp(
                                                                 dt.date.today() - dt.timedelta(days=365))},
                                                             {'label': '6 Meses', 'value': pd.Timestamp(
                                                                 dt.date.today() - dt.timedelta(days=(6 * 365) / 12))},
                                                             {'label': '3 Meses', 'value': pd.Timestamp(
                                                                 dt.date.today() - dt.timedelta(days=(3 * 365) / 12))}],
                                                         value=pd.Timestamp(
                                                             dt.date.today() - dt.timedelta(days=12 * 365)),
                                                         labelStyle={'display': 'inline-block', 'padding': '20px'},
                                                         style={}),
                                          ], style={'justify-content': 'center', 'display': 'flex',
                                                    'vertical-align': 'middle', 'width': '100%',
                                                    'font-size': 13}),
                                html.H4('Tipo de Competencia', style={'justify-content': 'center',
                                                                      'display': 'flex'}),
                                html.Div([dcc.Checklist(id='comp_type-picker',
                                                        options=[{'label': 'COPA MUNDO', 'value': 'A'},
                                                                 {'label': 'GRAND PRIX', 'value': 'GP'},
                                                                 {'label': 'MUNDIAL', 'value': 'CHM'},
                                                                 {'label': 'ZONAL', 'value': 'CHZ'}],
                                                        value=['A', 'GP'],
                                                        labelStyle={'margin-left': '25px'})

                                          ], style={'justify-content': 'center', 'display': 'flex',
                                                    'vertical-align': 'middle', 'width': '100%',
                                                    'font-size': 13})
                            ], style={})
                            ], style={'width': '60%'})

                        ], style={'display': 'flex', 'vertical-align': 'middle'})
                        ]),
                        html.Div([dcc.Graph(id='indres-graph')])
                    ])])]),

            html.Div([
                html.Div([
                    html.Div([
                        # html.Div([html.H2('Esgrimistas Individuales',style={'justify-content':'center',
                        #                                                          'display':'flex'}),
                        #        dcc.Dropdown(id='rkesg-picker',
                        #                    options=[{'label':i,'value':i}for i in rank['name'].unique()],
                        #                   multi=True,
                        #                  style={'width':'100%'},
                        #                 value=[rank['name'].unique()[0],rank['name'].unique()[1]])
                        #  ],style={'width':'40%'}),
                        html.Div([html.H2('Proyecciones Rankings Generales', style={'justify-content': 'center',
                                                                                    'display': 'flex'}),
                                  html.Div([
                                      html.Div([dcc.Checklist(id='rkweapon-picker',
                                                              options=[{'label': i, 'value': i} for i in
                                                                       rank['weapon'].unique()],
                                                              value=['epee', 'sabre', 'foil'],
                                                              labelStyle={'margin-left': '25px'})
                                                ], style={'justify-content': 'center', 'display': 'flex',
                                                          'vertical-align': 'middle',
                                                          'width': '50%'}),
                                      html.Div([dcc.Checklist(id='rkgender-picker',
                                                              options=[{'label': i, 'value': i} for i in
                                                                       rank['gender'].unique()],
                                                              value=['fem', 'masc'],
                                                              labelStyle={'margin-left': '25px'})
                                                ], style={'justify-content': 'center', 'display': 'flex',
                                                          'vertical-align': 'middle',
                                                          'width': '50%'})
                                  ], style={'width': '100%',
                                            'display': 'flex', 'vertical-align': 'middle'}),

                                  html.Div([html.H2(id='rank-range-select', style={'justify-content': 'center',
                                                                                   'display': 'flex'}),
                                            dcc.RangeSlider(id='rkrank-picker',
                                                            marks={1: '#1', 10: 'Top 10', 32: 'Top 32', 100: 'Top 100',
                                                                   156: '+++'},
                                                            min=1,
                                                            max=156,
                                                            value=[1, 100])

                                            ], style={})
                                  ], style={'width': '100%'})

                    ], style={'display': 'flex', 'vertical-align': 'middle'})]),

                html.Div([dcc.Graph(id='rank-graph')]),
                html.Div([
                    dcc.Markdown('''
                    * La Gráfica de Proyecciones del Ranking permite comparar la evolución del ranking de un esgrimista
                      en relación al ranking promedio de los esgrimistas a nivel mundial para un rango específico.

                      La gráfica visualiza el ranking promedio por edad de los esgrimistas que han logrado llegar al rango
                      de ranking escogido. Es decir, si el rango de ranking escogido es TOP 5, la gráfica mostrará el
                      ranking promedio por edad de los esgrimistas que han llegado a ser Top 5 del mundo en su carrera,
                      y cómo ha sido su progresión a lo largo de los años. De esta forma, es posible comparar si la curva
                      de ranking de un esgrimista individual va por la misma proyección del rango seleccionado, por encima
                      o por debajo.

                    ''')
                ], style={'margin-bottom': '75px'}),
                html.Div([
                    html.Div([dcc.Dropdown(id='results-event',
                                           options=[{'label': 'COPA MUNDO', 'value': 'COPA'},
                                                    {'label': 'GRAND PRIX', 'value': 'GP'},
                                                    {'label': 'CAMPEONATO DEL MUNDO', 'value': 'CHM'},
                                                    {'label': 'CAMPEONATO DE ZONA', 'value': 'CHZ'},
                                                    {'label': 'SATELITE', 'value': 'SA'}],
                                           value='COPA',
                                           style={'width': '85%', 'font-size': 15})
                              ], style={'justify-content': 'center', 'display': 'flex', 'width': '50%'}),
                    html.Div([dcc.RadioItems(id='results-round-picker',
                                             options=[{'label': 'T64', 'value': '-t64+'},
                                                      {'label': 'T32', 'value': '-t32+'},
                                                      {'label': 'T16', 'value': '-t16+'},
                                                      {'label': 'T8', 'value': '-t8+'},
                                                      {'label': 'Podium', 'value': '-podium'}],
                                             value='-t64+',
                                             labelStyle={'margin-left': '25px'})
                              ], style={'justify-content': 'center', 'display': 'flex', 'width': '50%'}),
                ], style={'display': 'flex', 'vertical-align': 'middle'}),
                html.Div([dcc.Graph(id='fieresults-graph')]),
                html.Div([
                    dcc.Markdown('''
                    * La Gráfica de Proyecciones de Resultados permite comparar los resultados deportivos alcanzados por edad
                      por un esgrimista específico en relación a los resultados promedio alcanzados por esgrimistas que han
                      llegado al rango de ranking seleccionado.

                      La gráfica visualiza los resultados promedio por edad de los esgrimistas que han logrado llegar al rango
                      de ranking escogido en términos de ingresos a la ronda específica escogida. Es decir, si el rango de ranking
                      escogido es TOP 5, la gráfica mostrará los ingresos promedio por edad a la ronda de competencia escogida
                      (ejemplo: Ingreso a Cuadro de 64) de los esgrimistas que han llegado a ser Top 5 del mundo en su carrera,
                      y cómo ha sido su progresión a lo largo de los años. De esta forma, es posible comparar si la curva de
                      resultados de un esgrimista individual va por la misma proyección del rango seleccionado, por encima o por
                      debajo.

                    ''')
                ])

            ], style={'padding': 5, 'font-size': 12})
        ])

    elif tab == 'tab-2':
        return html.Div([
            html.H3('Rendimiento Individual Nacional'),
            html.Div([
                html.Div([
                    dcc.Dropdown(id='nal-res-esg-picker',
                                 options=[{'label': i, 'value': i} for i in col_df['name'].unique()],
                                 multi=True,
                                 style={'width': '100%'},
                                 value=[]),
                    html.Div(id='tabla-individual-nacional'),
                    html.Div([
                        html.Div([html.Div([
                            html.Div([html.H4('Variables de Comparación', style={'justify-content': 'center',
                                                                                 'display': 'flex'}),
                                      dcc.Dropdown(id='yaxis-nal-res',
                                                   options=features,
                                                   value='POS')
                                      ], style={'width': '40%'}),
                            html.Div([html.Div([
                                html.H4('Periodos de tiempo', style={'justify-content': 'center',
                                                                     'display': 'flex'}),
                                # html.Div([dcc.DatePickerRange(id='nal-custom-date-range',
                                #                               month_format='MMMM Y',
                                #                               end_date_placeholder_text='MMMM Y',
                                #                               start_date_placeholder_text='MMMM Y',
                                #                               min_date_allowed=df['date'].min(),
                                #                               clearable=True, )
                                #
                                #           ], style={'justify-content': 'center', 'display': 'flex',
                                #                     'vertical-align': 'middle', 'width': '100%',
                                #                     'font-size': 13}),
                                html.Div([dcc.RadioItems(id='nal-timeframes',
                                                         options=[
                                                             {'label': 'Todo', 'value': pd.Timestamp(
                                                                 dt.date.today() - dt.timedelta(days=12 * 365))},
                                                             {'label': '2 Años', 'value': pd.Timestamp(
                                                                 dt.date.today() - dt.timedelta(days=2 * 365))},
                                                             {'label': '1 Año', 'value': pd.Timestamp(
                                                                 dt.date.today() - dt.timedelta(days=365))},
                                                             {'label': '6 Meses', 'value': pd.Timestamp(
                                                                 dt.date.today() - dt.timedelta(days=(6 * 365) / 12))},
                                                             {'label': '3 Meses', 'value': pd.Timestamp(
                                                                 dt.date.today() - dt.timedelta(days=(3 * 365) / 12))}],
                                                         value=pd.Timestamp(
                                                             dt.date.today() - dt.timedelta(days=12 * 365)),
                                                         labelStyle={'display': 'inline-block', 'padding': '20px'},
                                                         style={}),
                                          ], style={'justify-content': 'center', 'display': 'flex',
                                                    'vertical-align': 'middle', 'width': '100%',
                                                    'font-size': 13}),
                                html.H4('Categoria', style={'justify-content': 'center',
                                                            'display': 'flex'}),
                                html.Div([dcc.Checklist(id='nal-category',
                                                        options=[{'label': 'Mayores', 'value': 'S'},
                                                                 {'label': 'Juvenil', 'value': 'J'},
                                                                 {'label': 'Cadete', 'value': 'C'},
                                                                 {'label': 'M15', 'value': 'M15'}],
                                                        value=['J'],
                                                        labelStyle={'margin-left': '25px'})

                                          ], style={'justify-content': 'center', 'display': 'flex',
                                                    'vertical-align': 'middle', 'width': '100%',
                                                    'font-size': 13})
                            ], style={})
                            ], style={'width': '60%'})
                        ], style={'display': 'flex', 'vertical-align': 'middle'})
                        ]),
                        html.Div([dcc.Graph(id='nal-res-graph')])
                    ])])]),
        ])

    elif tab == 'tab-3':
        return html.Div([
            html.Div([dash_table.DataTable(columns=[{"name": i, "id": i} for i in
                                                    df.groupby(['name', 'country', 'weapon', 'gender'],
                                                               as_index=False).agg({'age': 'max',
                                                                                    'comp': 'count',
                                                                                    'POS': 'mean',
                                                                                    'T96+': 'sum',
                                                                                    'T64+': 'sum',
                                                                                    'Q': 'mean',
                                                                                    'PIND': 'mean',
                                                                                    'PVICT': 'mean',
                                                                                    'PTR': 'mean',
                                                                                    'PTD': 'mean',
                                                                                    'PT-DIFF': 'mean',
                                                                                    'PMTR': 'mean',
                                                                                    'PMTD': 'mean',
                                                                                    'PMT-DIFF': 'mean',
                                                                                    'TTR': 'mean',
                                                                                    'TTD': 'mean',
                                                                                    'TMT-DIFF': 'mean',
                                                                                    'TMVAVG': 'mean',
                                                                                    'PEXMPT': 'mean',
                                                                                    'PM1V%': 'mean',
                                                                                    'PM1&2V%': 'mean'}).columns],
                                           data=df.groupby(['name', 'country', 'weapon', 'gender'], as_index=False).agg(
                                               {'age': 'max',
                                                'comp': 'count',
                                                'POS': 'mean',
                                                'T96+': 'sum',
                                                'T64+': 'sum',
                                                'Q': 'mean',
                                                'PIND': 'mean',
                                                'PVICT': 'mean',
                                                'PTR': 'mean',
                                                'PTD': 'mean',
                                                'PT-DIFF': 'mean',
                                                'PMTR': 'mean',
                                                'PMTD': 'mean',
                                                'PMT-DIFF': 'mean',
                                                'TTR': 'mean',
                                                'TTD': 'mean',
                                                'TMT-DIFF': 'mean',
                                                'TMVAVG': 'mean',
                                                'PEXMPT': 'mean',
                                                'PM1V%': 'mean',
                                                'PM1&2V%': 'mean'}).round(3).to_dict('records'),
                                           sort_action="native",
                                           hidden_columns=[],
                                           sort_mode='multi',
                                           page_size=10,
                                           filter_action="native",
                                           style_table={'overflowX': 'scroll',
                                                        'width': '100%',
                                                        'minWidth': '100%'},
                                           fixed_columns={'headers': True, 'data': 1})], style={'margin-bottom': '75px',
                                                                                                'margin-top': '25px'}),
            # dcc.Graph(id='exercise',figure={'data':traces,'layout':layout})
            html.Div([
                html.Div([dcc.Dropdown(id='xaxis',
                                       options=features,
                                       value='PTR',
                                       style={'width': '85%', 'font-size': 15})
                          ], style={'justify-content': 'center', 'display': 'flex', 'width': '50%'}),
                html.Div([dcc.Dropdown(id='yaxis',
                                       options=features,
                                       value='POS',
                                       style={'width': '85%', 'font-size': 15})
                          ], style={'justify-content': 'center', 'display': 'flex', 'width': '50%'}),
            ], style={'display': 'flex', 'vertical-align': 'middle'}),
            html.Div([
                dcc.Graph(id='feature-graphic')
            ], style={})

        ])

    elif tab == 'tab-4':
        return html.Div([
            html.H3('Explicación de Variables'),
            dcc.Markdown('''

            ##### POS

            Posición final promedio del atleta.

            ##### PIND

            Indicador de poules.

            ##### PVICT

            Cantidad de Victorias en Poules.

            ##### PTR

            Toques recibidos totales en la ronda de poules.

            ##### PTD

            Toques dados totales en la ronda de poule.

            ##### PT-DIFF

            Diferencial total de toques recibidos y dados en la ronda de poule.

            ##### PMTR

            Promedio de toques recibidos por combate en la ronda de poule.

            ##### PMTD

            Promedio de toques dados por combate en la ronda de poule.

            ##### PMT-DIFF

            Promedio del diferencial de toques recibidos y dados por combate en la ronda de poule.

            ##### TTR

            Promedio de toques recibidos por combate en cuadro de eliminación directa.

            ##### TTD

            Promedio de toques dados por combate en cuadro de eliminación directa

            ##### TMT-DIFF

            Promedio del diferencial de toques recibidos y dados por combate de cuadro de
            eliminación directa

            ##### PM1V%
            Porcentaje de victorias del primer combate de la poule. Indica la frecuencia
            con la que el esgrimista gana su primer combate de la poule

            ##### PM1&2V%
            Porcentaje de victorias combinadas del primer y segundo combate de la poule.
            Indica la frecuencia con la que el esgrimista gana sus dos primeros combates
            de la poule

            ''')
        ])


# ___________________________________________________________________________________________

## CALLBACKS

# grafico
@app.callback(Output('feature-graphic', 'figure'),
              [Input('xaxis', 'value'),
               Input('yaxis', 'value')])
def update_graph(xaxis_name, yaxis_name):
    traces = []

    for weap in df['weapon'].unique():
        dff = df[df['weapon'] == weap]
        traces.append(go.Scatter(x=dff.groupby(xaxis_name)[[yaxis_name]].mean().index,
                                 y=dff.groupby(xaxis_name)[yaxis_name].mean(),
                                 mode='lines',
                                 name=weap))

    return {'data': traces, 'layout': go.Layout(title='{} vs {}'.format(xaxis_name, yaxis_name),
                                                xaxis=dict(title=xaxis_name),
                                                yaxis=dict(title=yaxis_name))}


# graficos tab ranking
@app.callback(Output('rank-graph', 'figure'),
              [Input('indres_esg-picker', 'value'),
               Input('rkweapon-picker', 'value'),
               Input('rkgender-picker', 'value'),
               Input('rkrank-picker', 'value')])
def update_graph(esg, weapons, genero, value_list):
    rklist = rank[(rank['ranking'] < value_list[1]) & (rank['ranking'] > value_list[0])]['name'].unique()
    rk = rank[(rank['gender'].isin(genero))]
    rk = rk[rk['name'].isin(rklist)]
    traces = []

    for weap in weapons:
        rank1 = rk[rk['weapon'] == weap]
        traces.append(go.Scatter(x=rank1.groupby('edad')[['ranking']].mean().index,
                                 y=rank1.groupby('edad')['ranking'].mean(),
                                 mode='lines',
                                 line={'dash': 'dot'},
                                 name=weap + ' - Ranking Promedio'))
    for e in esg:
        if rank[rank['name'] == e]['weapon'].nunique() == 1:
            traces.append(go.Scatter(x=rank[rank['name'] == e]['edad'],
                                     y=rank[rank['name'] == e]['ranking'],
                                     mode='lines',
                                     name=e + ' - ' + (rank[rank['name'] == e]['weapon'].unique()[0])))
        elif rank[rank['name'] == e]['weapon'].nunique() > 1:
            for wea in rank[rank['name'] == e]['weapon'].unique():
                traces.append(go.Scatter(x=rank[(rank['name'] == e) & (rank['weapon'] == wea)]['edad'],
                                         y=rank[(rank['name'] == e) & (rank['weapon'] == wea)]['ranking'],
                                         mode='lines',
                                         name=e + ' - ' + wea))

    return dict(data=traces, layout=go.Layout(title='Proyecciones del Ranking', xaxis=dict(title='Edad'),
                                              yaxis=dict(title='Ranking')))


# grafico resultados fie tab rankings -------------------------------------------------------------
@app.callback(Output('fieresults-graph', 'figure'),
              [Input('indres_esg-picker', 'value'),
               Input('rkweapon-picker', 'value'),
               Input('rkgender-picker', 'value'),
               Input('rkrank-picker', 'value'),
               Input('results-event', 'value'),
               Input('results-round-picker', 'value')])
def update_graph(esg, weapons, genero, value_list, event, rnd):
    rklist = rank[(rank['ranking'] < value_list[1]) & (rank['ranking'] > value_list[0])]['name'].unique()
    rk = rank[(rank['gender'].isin(genero))]
    rk = rk[rk['name'].isin(rklist)]
    traces = []

    for weap in weapons:
        rank1 = rk[rk['weapon'] == weap]
        traces.append(go.Scatter(x=rank1.groupby('edad')[[event + rnd]].mean().index,
                                 y=rank1.groupby('edad')[event + rnd].mean(),
                                 mode='lines',
                                 line={'dash': 'dot'},
                                 name=weap + ' - Resultados promedio'))
    for e in esg:
        if rank[rank['name'] == e]['weapon'].nunique() == 1:
            traces.append(go.Scatter(x=rank[rank['name'] == e]['edad'],
                                     y=rank[rank['name'] == e][event + rnd],
                                     mode='lines',
                                     name=e + ' - ' + (rank[rank['name'] == e]['weapon'].unique()[0])))
        elif rank[rank['name'] == e]['weapon'].nunique() > 1:
            for wea in rank[rank['name'] == e]['weapon'].unique():
                traces.append(go.Scatter(x=rank[(rank['name'] == e) & (rank['weapon'] == wea)]['edad'],
                                         y=rank[(rank['name'] == e) & (rank['weapon'] == wea)][event + rnd],
                                         mode='lines',
                                         name=e + ' - ' + wea))

    return dict(data=traces, layout=go.Layout(title='Proyecciones de Resultados', xaxis=dict(title='Edad'),
                                              yaxis=dict(title='Numero de Ingresos a la Ronda')))


##################################################################################################################
# ----------------------------------------------------------------------------------
@app.callback(
    Output('rank-range-select', 'children'),
    [Input('rkrank-picker', 'value')])
def update_value(value_list):
    if value_list[0] == 1 and value_list[1] != 156:
        return 'Top {}'.format(value_list[1])
    elif value_list[1] == 156:
        return 'Ranking desde {} al máximo posible'.format(value_list[0])
    elif value_list[0] == value_list[1]:
        return '{} en el Ranking'.format(value_list[0])
    else:
        return 'Ranking entre {} y {}'.format(value_list[0], value_list[1])


@app.callback(Output('tabla-individual', 'children'),
              [Input('indres_esg-picker', 'value'),
               Input('comp_type-picker', 'value'),
               Input('custom_date_range', 'start_date'),
               Input('custom_date_range', 'end_date'),
               Input('timeframes', 'value')])
def update_table_ind(esg, comp, start_date, end_date, time_frame):  #

    if (start_date is not None and end_date is not None):
        df1 = df[(df['date'] > start_date) & (df['date'] <= end_date)]
    elif (start_date is None and end_date is None):
        df1 = df[df['date'] > time_frame]
    df1 = df1[df1['type'].isin(comp)]
    dff = df1[df1['name'].isin(esg)].groupby(['name', 'country', 'weapon', 'gender'], as_index=False).agg({'age': 'max',
                                                                                                           'comp': 'count',
                                                                                                           'POS': 'mean',
                                                                                                           'T96+': 'sum',
                                                                                                           'T64+': 'sum',
                                                                                                           'Q': 'mean',
                                                                                                           'PIND': 'mean',
                                                                                                           'PVICT': 'mean',
                                                                                                           'PTR': 'mean',
                                                                                                           'PTD': 'mean',
                                                                                                           'PT-DIFF': 'mean',
                                                                                                           'PMTR': 'mean',
                                                                                                           'PMTD': 'mean',
                                                                                                           'PMT-DIFF': 'mean',
                                                                                                           'TTR': 'mean',
                                                                                                           'TTD': 'mean',
                                                                                                           'TMT-DIFF': 'mean',
                                                                                                           'TMVAVG': 'mean',
                                                                                                           'PEXMPT': 'mean',
                                                                                                           'PM1V%': 'mean',
                                                                                                           'PM1&2V%': 'mean'}).round(
        3)

    return dash_table.DataTable(id='table-ind', columns=[{"name": i, "id": i} for i in dff.columns],
                                data=dff.to_dict('records'),
                                sort_action="native",
                                hidden_columns=[],
                                sort_mode='multi',
                                page_size=10,
                                style_table={'overflowX': 'scroll',
                                             'width': '100%',
                                             'minWidth': '100%'},
                                fixed_columns={'headers': True, 'data': 1})


@app.callback(Output('indres-graph', 'figure'),
              [Input('indres_esg-picker', 'value'),
               Input('yaxis_indres', 'value'),
               Input('comp_type-picker', 'value'),
               Input('timeframes', 'value')])
def update_graph(esg, yaxis_indres, comp, time_frame):
    df1 = df[df['date'] > time_frame]
    df1.sort_values(by='date', inplace=True)
    df1 = df1[df1['type'].isin(comp)]

    traces = []
    df2 = df1[df1['name'].isin(esg)]

    for e in esg:
        if df2[df2['name'] == e]['weapon'].nunique() == 1:
            df3 = df2[df2['name'] == e]
            traces.append(go.Scatter(x=df3['date'],
                                     y=df3[yaxis_indres],
                                     mode='markers+lines+text',
                                     text=df3['POS'],
                                     textposition='top center',
                                     connectgaps=True,
                                     name=e + ' - ' + (df3[df3['name'] == e]['weapon'].unique()[0])))
        elif df2[df2['name'] == e]['weapon'].nunique() > 1:
            for wea in df2[df2['name'] == e]['weapon'].unique():
                df3 = df2[(df2['name'] == e) & (df2['weapon'] == wea)]
                traces.append(go.Scatter(x=df3['date'],
                                         y=df3[yaxis_indres],
                                         mode='markers+lines+text',
                                         text=df3['POS'],
                                         textposition='top center',
                                         connectgaps=True,
                                         name=e + ' - ' + wea))
    if yaxis_indres == 'POS' or yaxis_indres == 'PTR' or yaxis_indres == 'PMTR' or yaxis_indres == 'TTR':
        return dict(data=traces, layout=go.Layout(title='{}'.format(yaxis_indres),
                                                  legend_orientation="h",
                                                  # xaxis=dict(title='date'),
                                                  yaxis=dict(title='{}'.format(yaxis_indres),
                                                             autorange="reversed",
                                                             tickvals=[64, 32, 16, 8, 3])))
    else:
        return dict(data=traces, layout=go.Layout(title='{}'.format(yaxis_indres),
                                                  legend_orientation="h",
                                                  # xaxis=dict(title='date'),
                                                  yaxis=dict(title='{}'.format(yaxis_indres))))


# @app.callback(Output('indres-graph','figure'),
#              [Input('indres_esg-picker','value'),
#               Input('yaxis_indres','value'),
#               Input('comp_type-picker','value'),
#               Input('custom_date_range', 'start_date'),
#               Input('custom_date_range', 'end_date'),
#               Input('timeframes','value')])
# def update_graph(esg,yaxis_indres,comp,start_date,end_date,time_frame):
#
#    if (start_date is not None and end_date is not None):
#        df1 = df[(df['date'] > start_date) & (df['date'] <= end_date)]
#    elif (start_date is None and end_date is None):
#        df1 = df[df['date']>time_frame]
#    df1.sort_values(by='date',inplace=True)
#    df1 = df1[df1['type'].isin(comp)]

#    traces = []
#    df2 = df1[df1['name'].isin(esg)]
#
#    for e in esg:
#        if df2[df2['name']==e]['weapon'].nunique()==1:
#            df3 = df2[df2['name']==e]
#            traces.append(go.Scatter(x=df3['date'],
#                                     y=df3[yaxis_indres],
#                                     mode='markers+lines',
#                                     text=df3['place']+' - '+df3['type'],
#                                     connectgaps=True,
#                                     name=e+' - '+(df3[df3['name']==e]['weapon'].unique()[0])))
#        elif df2[df2['name']==e]['weapon'].nunique()>1:
#             for wea in df2[df2['name']==e]['weapon'].unique():
#                    df3 = df2[(df2['name']==e)&(df2['weapon']==wea)]
##                                             y=df3[yaxis_indres],
#                                             mode = 'markers+lines',
##                                             connectgaps=True,
#                                             name = e+' - '+wea))

#    return dict(data=traces,layout=go.Layout(title='{}'.format(yaxis_indres),
#                                             xaxis=dict(title='date'),
#                                             yaxis=dict(title='{}'.format(yaxis_indres))))

# @app.callback(
#    Output(component_id='fencer_name', component_property='children'),
#    [Input(component_id='indres_esg-picker', component_property='value')]
# )
# def update_output_div(input_value):
#    return '{}'.format(input_value[0])
#
# @app.callback(
#    Output(component_id='fencer_country', component_property='children'),
#    [Input(component_id='indres_esg-picker', component_property='value')]
# )
# def update_output_div(input_value):
#    return 'País: {}'.format(df[df['name']==input_value[0]]['country'].unique()[0])
#
#
# @app.callback(
#    Output(component_id='fencer_hand', component_property='children'),
#    [Input(component_id='indres_esg-picker', component_property='value')]
# )
# def update_output_div(input_value):
#    return 'Mano: {}'.format(rank[rank['name']==input_value[0]]['hand'].unique()[0])


# RESULTADOS COLOMBIA


@app.callback(Output('tabla-individual-nacional', 'children'),
              [Input('nal-res-esg-picker', 'value'),
               Input('nal-category', 'value'),
               # Input('nal-custom-date-range', 'start_date'),
               # Input('nal-custom-date-range', 'end_date'),
               Input('nal-timeframes', 'value')])
def update_table_ind_nal(esg, cat, time_frame):  #

    df1 = col_df[col_df['date'] > time_frame]
    df2 = df1[df1['category'].isin(cat)].copy()
    dff = df2[df2['name'].isin(esg)].groupby(['id', 'name', 'liga', 'weapon', 'gender'], as_index=False).agg(
        {'age': 'max',
         'comp': 'count',
         'POS': 'mean',
         # 'Q':'mean',
         'PIND': 'mean',
         'PVICT': 'mean',
         'PTR': 'mean',
         'PTD': 'mean',
         'PT-DIFF': 'mean',
         'PMTR': 'mean',
         'PMTD': 'mean',
         'PMT-DIFF': 'mean',
         'TTR': 'mean',
         'TTD': 'mean',
         'TMT-DIFF': 'mean',
         # 'TMVAVG':'mean',
         # 'PEXMPT':'mean',
         'PM1V%': 'mean',
         'PM1&2V%': 'mean'}).round(3)
    dff.sort_values(by='POS', ascending=True, inplace=True)

    return dash_table.DataTable(id='table-ind-nal',
                                columns=[{"name": i, "id": i} for i in dff.columns],
                                data=dff.to_dict('records'),
                                sort_action="native",
                                hidden_columns=[],
                                sort_mode='multi',
                                page_size=10,
                                style_table={'overflowX': 'scroll',
                                             'width': '100%',
                                             'minWidth': '100%'},
                                fixed_columns={'headers': True, 'data': 1})


@app.callback(Output('nal-res-graph', 'figure'),
              [Input('nal-res-esg-picker', 'value'),
               Input('yaxis-nal-res', 'value'),
               Input('nal-category', 'value'),
               Input('nal-timeframes', 'value')])
def update_nal_graph(esg, yaxis_indres, comp, time_frame):
    df1 = col_df[col_df['date'] > time_frame]
    df1.sort_values(by='date', inplace=True)
    df1 = df1[df1['category'].isin(comp)]
    df1['marker'] = np.where(df1['category'] == 'S', 'hexagram',
                             np.where(df1['category'] == 'J', 'square',
                                      np.where(df1['category'] == 'C', 'star-triangle-up', 'cross')))

    fig = go.Figure()

    df2 = df1[df1['name'].isin(esg)]

    for e in esg:
        if df2[df2['name'] == e]['weapon'].nunique() == 1:
            df3 = df2[df2['name'] == e]
            fig.add_trace(go.Scatter(x=df3['date'],
                                     y=df3[yaxis_indres],
                                     mode='markers+lines+text',
                                     marker=dict(size=10),
                                     marker_symbol=df3['marker'],
                                     text=round(df3[yaxis_indres], 2),
                                     textposition='middle left',
                                     showlegend=True,
                                     connectgaps=True,
                                     name=e + ' - ' + (df3[df3['name'] == e]['weapon'].unique()[0])))
    if yaxis_indres == 'POS' or yaxis_indres == 'PTR' or yaxis_indres == 'PMTR' or yaxis_indres == 'TTR':
        fig.update_layout(title='{}'.format(yaxis_indres),
                          legend_orientation="h",
                          yaxis=dict(title='{}'.format(yaxis_indres),
                                     autorange="reversed",
                                     tickvals=[64, 32, 16, 8, 3]))
    else:
        fig.update_layout(title='{}'.format(yaxis_indres),
                          legend_orientation="h",
                          yaxis=dict(title='{}'.format(yaxis_indres)))

    return fig


if __name__ == '__main__':
    app.run_server()
