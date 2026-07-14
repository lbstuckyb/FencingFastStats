import pandas as pd
import numpy as np

comp = pd.read_csv('new_results.csv')
comp.drop(columns=['Unnamed: 0'], inplace=True)

comp.drop(columns=['p1','p2', 'p3', 'p4', 'p5', 'p6','M'],inplace=True)

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
comp.loc[(comp.p1_tr == 0)&(comp.p1_result == 'D'),['p1_result', 'p1_td', 'p1_tr', 'p1_opp']]= np.nan
comp.loc[(comp.p2_tr == 0)&(comp.p2_result == 'D'),['p2_result', 'p2_td', 'p2_tr', 'p2_opp']]= np.nan
comp.loc[(comp.p3_tr == 0)&(comp.p3_result == 'D'),['p3_result', 'p3_td', 'p3_tr', 'p3_opp']]= np.nan
comp.loc[(comp.p4_tr == 0)&(comp.p4_result == 'D'),['p4_result', 'p4_td', 'p4_tr', 'p4_opp']]= np.nan
comp.loc[(comp.p5_tr == 0)&(comp.p5_result == 'D'),['p5_result', 'p5_td', 'p5_tr', 'p5_opp']]= np.nan
comp.loc[(comp.p6_tr == 0)&(comp.p6_result == 'D'),['p6_result', 'p6_td', 'p6_tr', 'p6_opp']]= np.nan

# Q == pasar la poule
colus =  'match_res_pre256','match_res_pre128', 'match_res_pre64','match_res_t64','match_res_t32','match_res_t16', 'match_res_t8', 'match_res_semi','match_res_final'
for col in colus:
    comp[col].fillna(value='',inplace=True)

comp['Q'] = comp['match_res_pre256']+comp['match_res_pre128']+comp[ 'match_res_pre64']+comp['match_res_t64']+comp['match_res_t32']+comp[
    'match_res_t16']+comp['match_res_t8']+comp['match_res_semi']+comp['match_res_final']
comp['Q'] = comp['Q'].apply(lambda x:len(x))
comp['Q'] = comp['Q'].apply(lambda x:1 if x!=0 else x)

comp['PEXMPT']=comp['poule_ind'].apply(lambda x: 0 if x>-1 else 1)

# nuevas columnas de analisis

comp['p_tr_mean'] = comp['tr_poules']/comp['p_matches']
comp['p_tr_std'] = comp[['p1_tr','p2_tr','p3_tr','p4_tr','p5_tr','p6_tr']].std(skipna=True,axis=1)
comp['p_td_mean'] = comp[['p1_td','p2_td','p3_td','p4_td','p5_td','p6_td']].mean(skipna=True,axis=1)
comp['p_td_std'] = comp[['p1_td','p2_td','p3_td','p4_td','p5_td','p6_td']].std(skipna=True,axis=1)
comp['poulematch_touch_diff'] = comp['p_td_mean']-comp['p_tr_mean']

comp['table_tr_mean'] = comp[['tr_pre256','tr_pre128','tr_pre64','tr_t64','tr_t32','tr_t16','tr_t8','tr_semi','tr_final']].mean(skipna=True,axis=1)
comp['table_tr_std'] = comp[['tr_pre256','tr_pre128','tr_pre64','tr_t64','tr_t32','tr_t16','tr_t8','tr_semi','tr_final']].std(skipna=True,axis=1)
comp['table_td_mean'] = comp[['td_pre256','td_pre128','td_pre64','td_t64','td_t32','td_t16','td_t8','td_semi','td_final']].mean(skipna=True,axis=1)
comp['table_td_std'] = comp[['td_pre256','td_pre128','td_pre64','td_t64','td_t32','td_t16','td_t8','td_semi','td_final']].std(skipna=True,axis=1)
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

comp['p1_result']=comp['p1_result'].apply(lambda x:1 if x=='V' else (0 if x=='D' else x))
comp['p2_result']=comp['p2_result'].apply(lambda x:1 if x=='V' else (0 if x=='D' else x))
comp['p3_result']=comp['p3_result'].apply(lambda x:1 if x=='V' else (0 if x=='D' else x))
comp['p4_result']=comp['p4_result'].apply(lambda x:1 if x=='V' else (0 if x=='D' else x))
comp['p5_result']=comp['p5_result'].apply(lambda x:1 if x=='V' else (0 if x=='D' else x))
comp['p6_result']=comp['p6_result'].apply(lambda x:1 if x=='V' else (0 if x=='D' else x))
comp['match_res_pre256']=comp['match_res_pre256'].apply(lambda x:1 if x=='V' else 0)
comp['match_res_pre128']=comp['match_res_pre128'].apply(lambda x:1 if x=='V' else 0)
comp['match_res_pre64']=comp['match_res_pre64'].apply(lambda x:1 if x=='V' else 0)
comp['match_res_t64']=comp['match_res_t64'].apply(lambda x:1 if x=='V' else 0)
comp['match_res_t32']=comp['match_res_t32'].apply(lambda x:1 if x=='V' else 0)
comp['match_res_t16']=comp['match_res_t16'].apply(lambda x:1 if x=='V' else 0)
comp['match_res_t8']=comp['match_res_t8'].apply(lambda x:1 if x=='V' else 0)
comp['match_res_semi']=comp['match_res_semi'].apply(lambda x:1 if x=='V' else 0)
comp['match_res_final']=comp['match_res_final'].apply(lambda x:1 if x=='V' else 0)

comp['PM1V%']=comp['p1_result']
comp['PM1&2V%']=comp['p1_result']*comp['p2_result']

# victorias promedio en cuadro
comp['TMVAVG'] = comp['match_res_pre256']+comp['match_res_pre128']+comp['match_res_pre64']+comp['match_res_t64']+comp['match_res_t32']+comp['match_res_t16']+comp['match_res_t8']+comp['match_res_semi']+comp['match_res_final']
comp['TMVAVG'] = comp[['TMVAVG','Q']].apply(lambda x: np.nan if x['Q']==0 else x['TMVAVG'], axis=1)

comp['T64+'] = comp['opp_t64'].apply(lambda x: 0 if pd.isnull(x) else 1)
comp['T96+'] = comp['opp_pre64'].apply(lambda x: 0 if pd.isnull(x) else 1)

print(comp.tail())


# import old data
df = pd.read_csv('../final_results/results3may2022.csv')


# concat new and oldd

final_df = pd.concat(objs=[df, comp], ignore_index=True, sort=False)
final_df.drop(columns=[col for col in final_df.columns if 'Unn' in col], inplace=True)

print(df.columns)
print(final_df.columns)

final_df.to_csv('../final_results/results15dec2022.csv')
final_df.to_csv('../data/updated_results.csv')
