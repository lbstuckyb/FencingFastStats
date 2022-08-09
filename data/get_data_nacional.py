from datetime import datetime

import pandas as pd
import numpy as np

results = pd.DataFrame()
results = pd.read_csv('COL.csv')
# results.drop('Unnamed: 0', inplace=True)
match = pd.DataFrame()
# ccc = [682, 683, 684, 685, 686, 687,
#        949,950,951,952,953,954,955,956,957,958,959,960,961,962,963,964,965,966,
#        988,989,990,991,992,
#        1090,1091,1092,1093,1094,1095,1096,1097,1098,1099,1100,1101,1102,1103,1104,1105,1106,1107,
#        1130,1131,1132,1137,1136,1138,
#        1154,1155,1156,1157,1158,1159,1160,1161,1162,1163,1164,1165,1166,1167,1168,1169,1170,1171,
#        1223,1224,1225,1229,1230,1231,
#        1265,1266,1267,1268,1269,1270,1271,1272,1273,1274,1275,1276,1277,1278,1279,1280,1281,1282,
#        1301,1302,1303,1307,1308,
#        1331,1332,1333,1334,1335,1337,1338,1339,1340,1341,1342,1343,1344,1345,1346,1347,1348, #,1336
#        1373,1374,1375,1384,1383,1377,1378,1376,1379,1380,1381,1382,1385,1386,1387,1388,1389,1390,
#        1409,1410,1411,1412,1413,1414,
#        1575,1573,1574,1576,1577,1578,1579,1580,1581,1582,1583,1584,1589,1586,1587,1590,1585,1588,
#        1591,1592,1593,1594,1595,1596,
#        1610,1651,1649,1650,1609,1653,1654,1655,1656,1611,1612,1657,1658,1660,1614,1659,1613,1615,
#        1661,1662,1663,1664,1616,# falta sfm15
#        1670,1671,1673,1669,1674,1672,1679,1676,1677,1678,1675,1680,1685,1683,1686,1684, #1681,1682 archivo cruzado
#        1711,1712,1715,1716,1719,1720,
#        1723,1725,1724,1727,1726,1728,1730,1731,1729,1732,1733,1734,1736,1737,1735,1738,1739,1740,
#        1741,1742,1743,1744,1745,1746,
#        1808,1807,1809,1810,1812,1813,1814,1815,1817,1818,1819,1820,1821,1822,1823, #,1811,1816,1824, no hubo
#        1828,1829,1831,1832,#1833, ,1830 sable valldupar
#        1855,1856,1857,1861,1862,1863,
#        1870,1869,1871,1873,1874,1875,1876,1878,1879,1880,1881,1882,1883,1884,1885, # ,1872,1877 incompleto
#        1891,1889,1890,1894,1893,1892,
#        1916,1919,1921,1922,1923,1924,1927,1928,1929,1930,1931,1932, #,1917,1918,1920,1925,1946,1933 incompleto
#        1937,1938,1939 #1934,1935,1936, incompletos
# ]
# ccc = [2050,2051,2052,2053,2054,2055,2056,2057,2058,2059,2060,2061,2062,2063,2064,2065,2066,2067,
#        2071,2072,2073,2074,2075,2076] # comp buga jun 2022

ccc = [2164,2165,2166,2167,2168,2169,
       2170,2171,2172,2173,2174,2175,
       # 2176,
       2177,2178,2179,2180,2181
       ] # comp GN medellin ago 2022


for e in ccc:
    df = pd.read_html('https://sistemainfo.fedesgrimacolombia.com/prueba_stats?prueba={}'.format(e), encoding='utf-8')
    fin = df[0]
    p = df[1]
    pm = df[2]
    t = df[3]

   # -------------------------------------- combates ------------------------------------

    poule = pm.copy()
    tablas = t.copy()
    info = fin.copy()

    poule.drop(axis=1, columns=['Poule', 'Match'], inplace=True)
    poule['Cuadro'] = 'poule'
    poule['DIF'] = poule['TD'] - poule['TR']
    poule.rename(columns={"ID": "id"}, inplace=True)
    tablas.rename(columns={"ID": "id"}, inplace=True)

    combates = pd.concat(objs=[poule, tablas], ignore_index=True, sort=False)
    combates = pd.merge(left=combates, right=info, on=['id'], how='outer')

    # -------------------------------------- resultados ----------------------------------

    # ------------------------ merge final + poule results ----------------------------
    p.columns = ['Poule', 'id', 'Nombre', 'Apellidos', 'poule_order', 'poule_vict',
       'td_polues', 'tr_poules', 'poule_ind', 'p_diff', 'rank_poule',
       'p_matches']
    p.drop(axis=1, columns=['Nombre','Apellidos'], inplace=True)
    comp = pd.merge(left=fin, right=p, on=['id'], how='outer')

    # ------------------------merge poule match results ------------------------------
    a = []
    for i in pm['Asalto #'].unique():
        i = 'pm{}'.format(i)
        a.append(i)

    for i in a:
        x = int(i[2])
        i = pm[pm['Asalto #'] == x].copy()
        i.columns = ['Poule', 'Match', 'id', 'Nombre', 'Apellido', 'Asalto #', 'p{}_td'.format(x), 'p{}_tr'.format(x),
                     'p{}_result'.format(x), 'p{}_opp_id'.format(x), 'p{}_opp_fn'.format(x), 'p{}_opp_ln'.format(x)]
        i.drop(axis=1, columns=['Poule', 'Match', 'Asalto #',
                                'Nombre', 'Apellido',
                                'p{}_opp_fn'.format(x), 'p{}_opp_ln'.format(x)], inplace=True)
        comp = pd.merge(left=comp, right=i, on=['id'], how='outer')

    # ----------------------- merge table results -------------------------------------
    t.columns = ['Cuadro', 'id', 'Nombre', 'Apellidos', 'TD', 'TR', 'DIF', 'Resultado',
       'ID oponente', 'Nombre.1', 'Apellidos.1']
    t.drop(axis=1, columns=['Nombre','Apellidos', 'Nombre.1', 'Apellidos.1'], inplace=True)

    b = []
    for i in t['Cuadro'].unique():
        i = 't{}'.format(i)
        b.append(i)

    for i in b:
        x = i[1:]
        i = t[t['Cuadro'] == x].copy()
        if len(x) < 4:
            i.columns = ['Cuadro', 'id', 'td_t{}'.format(x), 'tr_t{}'.format(x), 'match_dif_t{}'.format(x),
                         'match_res_t{}'.format(x), 't{}_opp_id'.format(x)]
        elif len(x) >= 4:
            i.columns = ['Cuadro', 'id', 'td_{}'.format(x), 'tr_{}'.format(x), 'match_dif_{}'.format(x),
                         'match_res_{}'.format(x), '{}_opp_id'.format(x)]
        i.drop(axis=1, columns=['Cuadro'], inplace=True)
        comp = pd.merge(left=comp, right=i, on=['id'], how='outer')
    comp['name'] = comp['first name']+' '+comp['last name']

    # print(comp.columns)

    # comp.drop(columns=['p1','p2', 'p3', 'p4', 'p5', 'p6','M'],inplace=True)

    # para eliminar los que no participaron
    comp.drop(comp[comp['final_pos']>900].index,inplace=True)
    comp.drop(comp[comp['weapon'].isnull()].index,inplace=True)
    comp.drop(comp[comp['tr_poules']==0].index,inplace=True)
    # para unificar los datos informativos de la competencia
    comp['weapon'] = comp['weapon'].apply(lambda x:x.strip())
    comp['category'] = comp['category'].apply(lambda x:x.strip())
    comp['gender'] = comp['gender'].apply(lambda x:x.strip())
    comp['event'] = comp['event'].apply(lambda x:x.strip())
    comp['type'] = comp['type'].apply(lambda x:x.strip())
    comp['place'] = comp['place'].apply(lambda x:x.strip())
    comp['date'] = comp['date'].apply(lambda x:x.split(' ')[0])
    comp['date'] = comp['date'].apply(lambda x:datetime.strptime(x,'%d-%m-%Y'))


    # eliminar los datos de poule de personas que no llegaron a la competencia
    # quitar las derrotas a 0 toques recibidos
    # comp.loc[(comp.p1_tr == 0)&(comp.p1_result == 'D'),['p1_result', 'p1_td', 'p1_tr', 'p1_opp']]= np.nan
    # comp.loc[(comp.p2_tr == 0)&(comp.p2_result == 'D'),['p2_result', 'p2_td', 'p2_tr', 'p2_opp']]= np.nan
    # comp.loc[(comp.p3_tr == 0)&(comp.p3_result == 'D'),['p3_result', 'p3_td', 'p3_tr', 'p3_opp']]= np.nan
    # comp.loc[(comp.p4_tr == 0)&(comp.p4_result == 'D'),['p4_result', 'p4_td', 'p4_tr', 'p4_opp']]= np.nan
    # comp.loc[(comp.p5_tr == 0)&(comp.p5_result == 'D'),['p5_result', 'p5_td', 'p5_tr', 'p5_opp']]= np.nan
    # comp.loc[(comp.p6_tr == 0)&(comp.p6_result == 'D'),['p6_result', 'p6_td', 'p6_tr', 'p6_opp']]= np.nan

    # Q == pasar la poule
    # colus =  'match_res_t64','match_res_t32','match_res_t16', 'match_res_t8', 'match_res_semi','match_res_final'
    # for col in colus:
    #     comp[col].fillna(value='',inplace=True)

    # comp['Q'] = comp['match_res_t64']+comp['match_res_t32']+comp[
    #     'match_res_t16']+comp['match_res_t8']+comp['match_res_semi']+comp['match_res_final']
    # comp['Q'] = comp['Q'].apply(lambda x:len(x))
    # comp['Q'] = comp['Q'].apply(lambda x:1 if x!=0 else x)
    #
    # comp['PEXMPT']=comp['poule_ind'].apply(lambda x: 0 if x>-1 else 1)

    # nuevas columnas de analisis
    comp['p_tr_mean'] = comp['tr_poules'] / comp['p_matches']
    comp['p_td_mean'] = comp[[col for col in comp.columns if '_td' in col]].mean(skipna=True,axis=1)

    comp['poulematch_touch_diff'] = comp['p_td_mean']-comp['p_tr_mean']
    #
    comp['table_tr_mean'] = comp[[col for col in comp.columns if 'tr_' in col]].mean(skipna=True,axis=1)
    comp['table_td_mean'] = comp[[col for col in comp.columns if 'td_' in col]].mean(skipna=True,axis=1)
    comp['tablematch_touch_diff'] = comp['table_td_mean']-comp['table_tr_mean']


    comp.rename(columns={'final_pos':'POS',
                       'competition':'comp',
                       'poule_ind':'PIND',
                       'poule_vict':'PVICT',
                       'tr_poules':'PTR',
                       'td_polues':'PTD',
                       'p_diff':'PT-DIFF',
                       'p_tr_mean':'PMTR',
                       'p_td_mean':'PMTD',
                       'poulematch_touch_diff':'PMT-DIFF',
                       'table_tr_mean':'TTR',
                       'table_td_mean':'TTD',
                       'tablematch_touch_diff':'TMT-DIFF'},inplace=True)


    for pm in ['p1_result','p2_result','p3_result','p4_result','p5_result','p6_result']:
        if pm in comp.columns:
            comp[pm]=comp[pm].apply(lambda x:1 if x=='V' else (0 if x=='D' else x))

    for tm in ['match_res_t64','match_res_t32','match_res_t16','match_res_t8',
               'match_res_semi','match_res_final']:
        if tm in comp.columns:
            comp[tm]=comp[tm].apply(lambda x:1 if x=='V' else (0 if x=='D' else x))

    comp['PM1V%']=comp['p1_result']
    comp['PM1&2V%']=comp['p1_result']*comp['p2_result']

    # # victorias promedio en cuadro
    comp['TMV'] = comp[[col for col in comp.columns if 'match_res' in col]].sum(axis=1)
    # comp['TMV%'] = comp['TMV']/len([col for col in comp.columns if 'match_res' in col])
    # comp['TMVAVG'] = comp[['TMVAVG','Q']].apply(lambda x: np.nan if x['Q']==0 else x['TMVAVG'], axis=1)
    #
    # comp['T64+'] = comp['opp_t64'].apply(lambda x: 0 if pd.isnull(x) else 1)
    # comp['T96+'] = comp['opp_pre64'].apply(lambda x: 0 if pd.isnull(x) else 1)



    results = pd.concat(objs=[results, comp], ignore_index=True, sort=False)
    print(e)

print(results)
results.drop_duplicates(subset=['id', 'comp', 'date', 'category'],
                       keep='first', inplace=True, ignore_index=True)



results.to_csv('./COL.csv')