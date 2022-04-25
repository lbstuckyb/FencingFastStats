import pandas as pd
import numpy as np

# df = pd.read_html('https://sistemainfo.fedesgrimacolombia.com/prueba_stats?prueba=1823')
# print(df)



results = pd.DataFrame()
match = pd.DataFrame()
ccc = [1657,1727,1823,1884]


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
    #comp['date'] = comp['date'].apply(lambda x:x.split(' ')[0])
    #comp['date'] = comp['date'].apply(lambda x:datetime.strptime(x,'%m/%d/%Y'))


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

print(results)



results.to_csv('./efj.csv')