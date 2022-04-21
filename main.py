import numpy as np
import pandas as pd
import functools


def get_competition(info=None,
                    hj1=None,
                    hj2=None,
                    hj3=None,
                    hj4=None,
                    hj5=None,
                    hj6=None):

    info = info

    h1 = hj1  # poules
    h2 = hj2  # resultados de la poule
    h3 = hj3  # tablas preliminares
    h4 = hj4  # tablas 256 a 16
    h5 = hj5  # tablas T8 a final
    h6 = hj6  # resultados finales

    ###### arreglando las poules ################

    for i in range(len(h1)):
        if type(h1.loc[i, (h1.columns[0])]) == str and len(h1.loc[i, (h1.columns[0])]) > 5 and h1.loc[i, (
        h1.columns[0])].replace(' ', '')[:4] != 'Árbi' and h1.loc[i, (h1.columns[0])].replace(' ', '')[:4] != 'POOL':
            h1.loc[i, 'n'] = 1

    for i in range(len(h1)):
        if h1.loc[i, 'n'] == 1:
            h1.loc[i, 'poule_order'] = h1.loc[i - 2, (h1.columns[0])]
            h1.loc[i, 'p1'] = h1.loc[i + 1, (h1.columns[0])]
            h1.loc[i, 'p2'] = h1.loc[i + 2, (h1.columns[0])]
            h1.loc[i, 'p3'] = h1.loc[i + 3, (h1.columns[0])]
            h1.loc[i, 'p4'] = h1.loc[i + 4, (h1.columns[0])]
            h1.loc[i, 'p5'] = h1.loc[i + 5, (h1.columns[0])]
            if type(h1.loc[i + 6, (h1.columns[0])]) == str:
                h1.loc[i, 'p6'] = h1.loc[i + 6, (h1.columns[0])]
            else:
                h1.loc[i, 'p6'] = ''

    h1.dropna(axis=0, thresh=3, inplace=True)
    h1.rename(columns={h1.columns[0]: 'name'}, inplace=True)
    h1.reset_index(inplace=True)
    h1['poules'] = h1['p1'] + h1['p2'] + h1['p3'] + h1['p4'] + h1['p5'] + h1['p6']
    h1['poullen'] = h1['poules'].apply(lambda x: len(x))
    h1['p_matches'] = h1['poullen'] / 3
    h1['id'] = 'a'
    for i in range(len(h1)):
        h1['id'][i] = h1['name'][i].replace(' ', '')[:11].lower()

    h1['poule_order'] = pd.to_numeric(h1['poule_order'], downcast='integer')

    from textwrap import wrap

    for i in range(len(h1)):
        if h1.loc[i, 'poule_order'] == 1 and h1.loc[i, 'p_matches'] == 5:  # first seed in poule

            # combate 1
            h1.loc[i, 'p1_result'] = wrap(h1.loc[i, 'poules'], 3)[0].split('/')[
                0]  # resultado del combate (victoria o derrota (V - D)
            h1.loc[i, 'p1_td'] = wrap(h1.loc[i, 'poules'], 3)[0].split('/')[1]  # Toques Dados en el combate
            h1.loc[i, 'p1_tr'] = wrap(h1.loc[i + 1, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 1)].split('/')[
                1]  # Toques Recibidos en el combate
            h1.loc[i, 'p1_opp'] = h1.loc[i + 1, 'id']  # oponente del combate

            # combate 2
            h1.loc[i, 'p2_result'] = wrap(h1.loc[i, 'poules'], 3)[1].split('/')[0]  # resultado
            h1.loc[i, 'p2_td'] = wrap(h1.loc[i, 'poules'], 3)[1].split('/')[1]  # dados
            h1.loc[i, 'p2_tr'] = wrap(h1.loc[i + 2, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 1)].split('/')[1]  # recibidos
            h1.loc[i, 'p2_opp'] = h1.loc[i + 2, 'id']  # rival

            # combate 3
            h1.loc[i, 'p3_result'] = wrap(h1.loc[i, 'poules'], 3)[4].split('/')[0]  # resultado
            h1.loc[i, 'p3_td'] = wrap(h1.loc[i, 'poules'], 3)[4].split('/')[1]  # dados
            h1.loc[i, 'p3_tr'] = wrap(h1.loc[i + 5, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 1)].split('/')[1]  # recibidos
            h1.loc[i, 'p3_opp'] = h1.loc[i + 5, 'id']  # rival

            # combate 4
            h1.loc[i, 'p4_result'] = wrap(h1.loc[i, 'poules'], 3)[3].split('/')[0]  # resultado
            h1.loc[i, 'p4_td'] = wrap(h1.loc[i, 'poules'], 3)[3].split('/')[1]  # dados
            h1.loc[i, 'p4_tr'] = wrap(h1.loc[i + 4, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 1)].split('/')[1]  # recibidos
            h1.loc[i, 'p4_opp'] = h1.loc[i + 4, 'id']  # rival

            # combate 5
            h1.loc[i, 'p5_result'] = wrap(h1.loc[i, 'poules'], 3)[2].split('/')[0]  # resultado
            h1.loc[i, 'p5_td'] = wrap(h1.loc[i, 'poules'], 3)[2].split('/')[1]  # dados
            h1.loc[i, 'p5_tr'] = wrap(h1.loc[i + 3, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 1)].split('/')[1]  # recibidos
            h1.loc[i, 'p5_opp'] = h1.loc[i + 3, 'id']  # rival

        elif h1.loc[i, 'poule_order'] == 2 and h1.loc[i, 'p_matches'] == 5:  # second seed in poule

            # combate 1
            h1.loc[i, 'p1_result'] = wrap(h1.loc[i, 'poules'], 3)[0].split('/')[0]  # resultado
            h1.loc[i, 'p1_td'] = wrap(h1.loc[i, 'poules'], 3)[0].split('/')[1]  # dados
            h1.loc[i, 'p1_tr'] = wrap(h1.loc[i - 1, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 2)].split('/')[
                1]  # OJOOOO CUANDO EL MAN ESTA MAS ARRIBA EN EL CUADRO DE LA POULE ES (-2) ES DECIR SI RESTA EN LA i entonces es poule order -2
            h1.loc[i, 'p1_opp'] = h1.loc[i - 1, 'id']  # rival

            # combate 2
            h1.loc[i, 'p2_result'] = wrap(h1.loc[i, 'poules'], 3)[4].split('/')[0]  # resultado
            h1.loc[i, 'p2_td'] = wrap(h1.loc[i, 'poules'], 3)[4].split('/')[1]  # dados
            h1.loc[i, 'p2_tr'] = wrap(h1.loc[i + 4, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 1)].split('/')[1]  # recibidos
            h1.loc[i, 'p2_opp'] = h1.loc[i + 4, 'id']  # rival

            # combate 3
            h1.loc[i, 'p3_result'] = wrap(h1.loc[i, 'poules'], 3)[2].split('/')[0]  # resultado
            h1.loc[i, 'p3_td'] = wrap(h1.loc[i, 'poules'], 3)[2].split('/')[1]  # dados
            h1.loc[i, 'p3_tr'] = wrap(h1.loc[i + 2, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 1)].split('/')[1]  # recibidos
            h1.loc[i, 'p3_opp'] = h1.loc[i + 2, 'id']  # rival

            # combate 4
            h1.loc[i, 'p4_result'] = wrap(h1.loc[i, 'poules'], 3)[1].split('/')[0]  # resultado
            h1.loc[i, 'p4_td'] = wrap(h1.loc[i, 'poules'], 3)[1].split('/')[1]  # dados
            h1.loc[i, 'p4_tr'] = wrap(h1.loc[i + 1, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 1)].split('/')[1]  # recibidos
            h1.loc[i, 'p4_opp'] = h1.loc[i + 1, 'id']  # rival

            # combate 5
            h1.loc[i, 'p5_result'] = wrap(h1.loc[i, 'poules'], 3)[3].split('/')[0]  # resultado
            h1.loc[i, 'p5_td'] = wrap(h1.loc[i, 'poules'], 3)[3].split('/')[1]  # dados
            h1.loc[i, 'p5_tr'] = wrap(h1.loc[i + 3, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 1)].split('/')[1]  # recibidos
            h1.loc[i, 'p5_opp'] = h1.loc[i + 3, 'id']  # rival

        elif h1.loc[i, 'poule_order'] == 3 and h1.loc[i, 'p_matches'] == 5:  # third seed in poule

            # combate 1
            h1.loc[i, 'p1_result'] = wrap(h1.loc[i, 'poules'], 3)[2].split('/')[0]  # resultado
            h1.loc[i, 'p1_td'] = wrap(h1.loc[i, 'poules'], 3)[2].split('/')[1]  # dados
            h1.loc[i, 'p1_tr'] = wrap(h1.loc[i + 1, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 1)].split('/')[1]  # recibidos
            h1.loc[i, 'p1_opp'] = h1.loc[i + 1, 'id']  # rival

            # combate 2
            h1.loc[i, 'p2_result'] = wrap(h1.loc[i, 'poules'], 3)[0].split('/')[0]  # resultado
            h1.loc[i, 'p2_td'] = wrap(h1.loc[i, 'poules'], 3)[0].split('/')[1]  # dados
            h1.loc[i, 'p2_tr'] = wrap(h1.loc[i - 2, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 2)].split('/')[1]  # recibidos
            h1.loc[i, 'p2_opp'] = h1.loc[i - 2, 'id']  # rival

            # combate 3
            h1.loc[i, 'p3_result'] = wrap(h1.loc[i, 'poules'], 3)[3].split('/')[0]  # resultado
            h1.loc[i, 'p3_td'] = wrap(h1.loc[i, 'poules'], 3)[3].split('/')[1]  # dados
            h1.loc[i, 'p3_tr'] = wrap(h1.loc[i + 2, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 1)].split('/')[1]  # recibidos
            h1.loc[i, 'p3_opp'] = h1.loc[i + 2, 'id']  # rival

            # combate 4
            h1.loc[i, 'p4_result'] = wrap(h1.loc[i, 'poules'], 3)[1].split('/')[0]  # resultado
            h1.loc[i, 'p4_td'] = wrap(h1.loc[i, 'poules'], 3)[1].split('/')[1]  # dados
            h1.loc[i, 'p4_tr'] = wrap(h1.loc[i - 1, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 2)].split('/')[1]  # recibidos
            h1.loc[i, 'p4_opp'] = h1.loc[i - 1, 'id']  # rival

            # combate 5
            h1.loc[i, 'p5_result'] = wrap(h1.loc[i, 'poules'], 3)[4].split('/')[0]  # resultado
            h1.loc[i, 'p5_td'] = wrap(h1.loc[i, 'poules'], 3)[4].split('/')[1]  # dados
            h1.loc[i, 'p5_tr'] = wrap(h1.loc[i + 3, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 1)].split('/')[1]  # recibidos
            h1.loc[i, 'p5_opp'] = h1.loc[i + 3, 'id']  # rival

        elif h1.loc[i, 'poule_order'] == 4 and h1.loc[i, 'p_matches'] == 5:  # fourth seed in poule

            # combate 1
            h1.loc[i, 'p1_result'] = wrap(h1.loc[i, 'poules'], 3)[2].split('/')[0]  # resultado
            h1.loc[i, 'p1_td'] = wrap(h1.loc[i, 'poules'], 3)[2].split('/')[1]  # dados
            h1.loc[i, 'p1_tr'] = wrap(h1.loc[i - 1, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 2)].split('/')[1]  # recibidos
            h1.loc[i, 'p1_opp'] = h1.loc[i - 1, 'id']  # rival

            # combate 2
            h1.loc[i, 'p2_result'] = wrap(h1.loc[i, 'poules'], 3)[3].split('/')[
                0]  # resultado (se cambia el parentesis antes del split)
            h1.loc[i, 'p2_td'] = wrap(h1.loc[i, 'poules'], 3)[3].split('/')[
                1]  # dados     (se cambia el parentesis antes del split)
            h1.loc[i, 'p2_tr'] = wrap(h1.loc[i + 1, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 1)].split('/')[
                1]  # recibidos (se cambia el suma del i)
            h1.loc[i, 'p2_opp'] = h1.loc[i + 1, 'id']  # rival (se cambia el suma del i)

            # combate 3
            h1.loc[i, 'p3_result'] = wrap(h1.loc[i, 'poules'], 3)[1].split('/')[0]  # resultado
            h1.loc[i, 'p3_td'] = wrap(h1.loc[i, 'poules'], 3)[1].split('/')[1]  # dados
            h1.loc[i, 'p3_tr'] = wrap(h1.loc[i - 2, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 2)].split('/')[1]  # recibidos
            h1.loc[i, 'p3_opp'] = h1.loc[i - 2, 'id']  # rival

            # combate 4
            h1.loc[i, 'p4_result'] = wrap(h1.loc[i, 'poules'], 3)[4].split('/')[0]  # resultado
            h1.loc[i, 'p4_td'] = wrap(h1.loc[i, 'poules'], 3)[4].split('/')[1]  # dados
            h1.loc[i, 'p4_tr'] = wrap(h1.loc[i + 2, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 1)].split('/')[1]  # recibidos
            h1.loc[i, 'p4_opp'] = h1.loc[i + 2, 'id']  # rival

            # combate 5
            h1.loc[i, 'p5_result'] = wrap(h1.loc[i, 'poules'], 3)[0].split('/')[0]  # resultado
            h1.loc[i, 'p5_td'] = wrap(h1.loc[i, 'poules'], 3)[0].split('/')[1]  # dados
            h1.loc[i, 'p5_tr'] = wrap(h1.loc[i - 3, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 2)].split('/')[1]  # recibidos
            h1.loc[i, 'p5_opp'] = h1.loc[i - 3, 'id']  # rival

        elif h1.loc[i, 'poule_order'] == 5 and h1.loc[i, 'p_matches'] == 5:  # fifth seed in poule

            # combate 1
            h1.loc[i, 'p1_result'] = wrap(h1.loc[i, 'poules'], 3)[4].split('/')[0]  # resultado
            h1.loc[i, 'p1_td'] = wrap(h1.loc[i, 'poules'], 3)[4].split('/')[1]  # dados
            h1.loc[i, 'p1_tr'] = wrap(h1.loc[i + 1, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 1)].split('/')[1]  # recibidos
            h1.loc[i, 'p1_opp'] = h1.loc[i + 1, 'id']  # rival

            # combate 2
            h1.loc[i, 'p2_result'] = wrap(h1.loc[i, 'poules'], 3)[3].split('/')[
                0]  # resultado (se cambia el parentesis antes del split)
            h1.loc[i, 'p2_td'] = wrap(h1.loc[i, 'poules'], 3)[3].split('/')[
                1]  # dados     (se cambia el parentesis antes del split)
            h1.loc[i, 'p2_tr'] = wrap(h1.loc[i - 1, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 2)].split('/')[
                1]  # recibidos (se cambia el suma del i)
            h1.loc[i, 'p2_opp'] = h1.loc[i - 1, 'id']  # rival (se cambia el suma del i)

            # combate 3
            h1.loc[i, 'p3_result'] = wrap(h1.loc[i, 'poules'], 3)[2].split('/')[0]  # resultado
            h1.loc[i, 'p3_td'] = wrap(h1.loc[i, 'poules'], 3)[2].split('/')[1]  # dados
            h1.loc[i, 'p3_tr'] = wrap(h1.loc[i - 2, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 2)].split('/')[1]  # recibidos
            h1.loc[i, 'p3_opp'] = h1.loc[i - 2, 'id']  # rival

            # combate 4
            h1.loc[i, 'p4_result'] = wrap(h1.loc[i, 'poules'], 3)[0].split('/')[0]  # resultado
            h1.loc[i, 'p4_td'] = wrap(h1.loc[i, 'poules'], 3)[0].split('/')[1]  # dados
            h1.loc[i, 'p4_tr'] = wrap(h1.loc[i - 4, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 2)].split('/')[1]  # recibidos
            h1.loc[i, 'p4_opp'] = h1.loc[i - 4, 'id']  # rival

            # combate 5
            h1.loc[i, 'p5_result'] = wrap(h1.loc[i, 'poules'], 3)[1].split('/')[0]  # resultado
            h1.loc[i, 'p5_td'] = wrap(h1.loc[i, 'poules'], 3)[1].split('/')[1]  # dados
            h1.loc[i, 'p5_tr'] = wrap(h1.loc[i - 3, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 2)].split('/')[1]  # recibidos
            h1.loc[i, 'p5_opp'] = h1.loc[i - 3, 'id']

        elif h1.loc[i, 'poule_order'] == 6 and h1.loc[i, 'p_matches'] == 5:  # sixth seed in poule

            # combate 1
            h1.loc[i, 'p1_result'] = wrap(h1.loc[i, 'poules'], 3)[4].split('/')[0]  # resultado
            h1.loc[i, 'p1_td'] = wrap(h1.loc[i, 'poules'], 3)[4].split('/')[1]  # dados
            h1.loc[i, 'p1_tr'] = wrap(h1.loc[i - 1, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 2)].split('/')[1]  # recibidos
            h1.loc[i, 'p1_opp'] = h1.loc[i - 1, 'id']  # rival

            # combate 2
            h1.loc[i, 'p2_result'] = wrap(h1.loc[i, 'poules'], 3)[1].split('/')[
                0]  # resultado (se cambia el parentesis antes del split)
            h1.loc[i, 'p2_td'] = wrap(h1.loc[i, 'poules'], 3)[1].split('/')[
                1]  # dados     (se cambia el parentesis antes del split)
            h1.loc[i, 'p2_tr'] = wrap(h1.loc[i - 4, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 2)].split('/')[
                1]  # recibidos (se cambia el suma del i)
            h1.loc[i, 'p2_opp'] = h1.loc[i - 4, 'id']  # rival (se cambia el suma del i)

            # combate 3
            h1.loc[i, 'p3_result'] = wrap(h1.loc[i, 'poules'], 3)[0].split('/')[0]  # resultado
            h1.loc[i, 'p3_td'] = wrap(h1.loc[i, 'poules'], 3)[0].split('/')[1]  # dados
            h1.loc[i, 'p3_tr'] = wrap(h1.loc[i - 5, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 2)].split('/')[1]  # recibidos
            h1.loc[i, 'p3_opp'] = h1.loc[i - 5, 'name']  # rival

            # combate 4
            h1.loc[i, 'p4_result'] = wrap(h1.loc[i, 'poules'], 3)[3].split('/')[0]  # resultado
            h1.loc[i, 'p4_td'] = wrap(h1.loc[i, 'poules'], 3)[3].split('/')[1]  # dados
            h1.loc[i, 'p4_tr'] = wrap(h1.loc[i - 2, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 2)].split('/')[1]  # recibidos
            h1.loc[i, 'p4_opp'] = h1.loc[i - 2, 'id']  # rival

            # combate 5
            h1.loc[i, 'p5_result'] = wrap(h1.loc[i, 'poules'], 3)[2].split('/')[0]  # resultado
            h1.loc[i, 'p5_td'] = wrap(h1.loc[i, 'poules'], 3)[2].split('/')[1]  # dados
            h1.loc[i, 'p5_tr'] = wrap(h1.loc[i - 3, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 2)].split('/')[1]  # recibidos
            h1.loc[i, 'p5_opp'] = h1.loc[i - 3, 'id']

    # descomponiendo la poule de seis (7)

    for i in range(len(h1)):
        if h1.loc[i, 'poule_order'] == 1 and h1.loc[i, 'p_matches'] == 6:  # first seed in poule

            # combate 1
            h1.loc[i, 'p1_result'] = wrap(h1.loc[i, 'poules'], 3)[2].split('/')[
                0]  # resultado del combate (victoria o derrota (V - D)
            h1.loc[i, 'p1_td'] = wrap(h1.loc[i, 'poules'], 3)[2].split('/')[1]  # Toques Dados en el combate
            h1.loc[i, 'p1_tr'] = wrap(h1.loc[i + 3, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 1)].split('/')[
                1]  # Toques Recibidos en el combate
            h1.loc[i, 'p1_opp'] = h1.loc[i + 3, 'id']  # oponente del combate

            # combate 2
            h1.loc[i, 'p2_result'] = wrap(h1.loc[i, 'poules'], 3)[5].split('/')[0]  # resultado
            h1.loc[i, 'p2_td'] = wrap(h1.loc[i, 'poules'], 3)[5].split('/')[1]  # dados
            h1.loc[i, 'p2_tr'] = wrap(h1.loc[i + 6, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 1)].split('/')[1]  # recibidos
            h1.loc[i, 'p2_opp'] = h1.loc[i + 6, 'id']  # rival

            # combate 3
            h1.loc[i, 'p3_result'] = wrap(h1.loc[i, 'poules'], 3)[3].split('/')[0]  # resultado
            h1.loc[i, 'p3_td'] = wrap(h1.loc[i, 'poules'], 3)[3].split('/')[1]  # dados
            h1.loc[i, 'p3_tr'] = wrap(h1.loc[i + 4, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 1)].split('/')[1]  # recibidos
            h1.loc[i, 'p3_opp'] = h1.loc[i + 4, 'id']  # rival

            # combate 4
            h1.loc[i, 'p4_result'] = wrap(h1.loc[i, 'poules'], 3)[1].split('/')[0]  # resultado
            h1.loc[i, 'p4_td'] = wrap(h1.loc[i, 'poules'], 3)[1].split('/')[1]  # dados
            h1.loc[i, 'p4_tr'] = wrap(h1.loc[i + 2, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 1)].split('/')[1]  # recibidos
            h1.loc[i, 'p4_opp'] = h1.loc[i + 2, 'id']  # rival

            # combate 5
            h1.loc[i, 'p5_result'] = wrap(h1.loc[i, 'poules'], 3)[4].split('/')[0]  # resultado
            h1.loc[i, 'p5_td'] = wrap(h1.loc[i, 'poules'], 3)[4].split('/')[1]  # dados
            h1.loc[i, 'p5_tr'] = wrap(h1.loc[i + 5, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 1)].split('/')[1]  # recibidos
            h1.loc[i, 'p5_opp'] = h1.loc[i + 5, 'id']  # rival

            # combate 6
            h1.loc[i, 'p6_result'] = wrap(h1.loc[i, 'poules'], 3)[0].split('/')[0]  # resultado
            h1.loc[i, 'p6_td'] = wrap(h1.loc[i, 'poules'], 3)[0].split('/')[1]  # dados
            h1.loc[i, 'p6_tr'] = wrap(h1.loc[i + 1, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 1)].split('/')[1]  # recibidos
            h1.loc[i, 'p6_opp'] = h1.loc[i + 1, 'id']  # rival

        elif h1.loc[i, 'poule_order'] == 2 and h1.loc[i, 'p_matches'] == 6:  # second seed in poule

            # combate 1
            h1.loc[i, 'p1_result'] = wrap(h1.loc[i, 'poules'], 3)[3].split('/')[
                0]  # resultado del combate (victoria o derrota (V - D)
            h1.loc[i, 'p1_td'] = wrap(h1.loc[i, 'poules'], 3)[3].split('/')[1]  # Toques Dados en el combate
            h1.loc[i, 'p1_tr'] = wrap(h1.loc[i + 3, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 1)].split('/')[
                1]  # Toques Recibidos en el combate
            h1.loc[i, 'p1_opp'] = h1.loc[i + 3, 'id']  # oponente del combate

            # combate 2
            h1.loc[i, 'p2_result'] = wrap(h1.loc[i, 'poules'], 3)[1].split('/')[0]  # resultado
            h1.loc[i, 'p2_td'] = wrap(h1.loc[i, 'poules'], 3)[1].split('/')[1]  # dados
            h1.loc[i, 'p2_tr'] = wrap(h1.loc[i + 1, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 1)].split('/')[1]  # recibidos
            h1.loc[i, 'p2_opp'] = h1.loc[i + 1, 'id']  # rival

            # combate 3
            h1.loc[i, 'p3_result'] = wrap(h1.loc[i, 'poules'], 3)[4].split('/')[0]  # resultado
            h1.loc[i, 'p3_td'] = wrap(h1.loc[i, 'poules'], 3)[4].split('/')[1]  # dados
            h1.loc[i, 'p3_tr'] = wrap(h1.loc[i + 4, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 1)].split('/')[1]  # recibidos
            h1.loc[i, 'p3_opp'] = h1.loc[i + 4, 'id']  # rival

            # combate 4
            h1.loc[i, 'p4_result'] = wrap(h1.loc[i, 'poules'], 3)[5].split('/')[0]  # resultado
            h1.loc[i, 'p4_td'] = wrap(h1.loc[i, 'poules'], 3)[5].split('/')[1]  # dados
            h1.loc[i, 'p4_tr'] = wrap(h1.loc[i + 5, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 1)].split('/')[1]  # recibidos
            h1.loc[i, 'p4_opp'] = h1.loc[i + 5, 'id']  # rival

            # combate 5
            h1.loc[i, 'p5_result'] = wrap(h1.loc[i, 'poules'], 3)[2].split('/')[0]  # resultado
            h1.loc[i, 'p5_td'] = wrap(h1.loc[i, 'poules'], 3)[2].split('/')[1]  # dados
            h1.loc[i, 'p5_tr'] = wrap(h1.loc[i + 2, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 1)].split('/')[1]  # recibidos
            h1.loc[i, 'p5_opp'] = h1.loc[i + 2, 'id']  # rival

            # combate 6
            h1.loc[i, 'p6_result'] = wrap(h1.loc[i, 'poules'], 3)[0].split('/')[0]  # resultado
            h1.loc[i, 'p6_td'] = wrap(h1.loc[i, 'poules'], 3)[0].split('/')[1]  # dados
            h1.loc[i, 'p6_tr'] = wrap(h1.loc[i - 1, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 2)].split('/')[1]  # recibidos
            h1.loc[i, 'p6_opp'] = h1.loc[i - 1, 'id']  # rival

        elif h1.loc[i, 'poule_order'] == 3 and h1.loc[i, 'p_matches'] == 6:  # third seed in poule

            # combate 1
            h1.loc[i, 'p1_result'] = wrap(h1.loc[i, 'poules'], 3)[4].split('/')[
                0]  # resultado del combate (victoria o derrota (V - D)
            h1.loc[i, 'p1_td'] = wrap(h1.loc[i, 'poules'], 3)[4].split('/')[1]  # Toques Dados en el combate
            h1.loc[i, 'p1_tr'] = wrap(h1.loc[i + 3, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 1)].split('/')[
                1]  # Toques Recibidos en el combate
            h1.loc[i, 'p1_opp'] = h1.loc[i + 3, 'id']  # oponente del combate

            # combate 2
            h1.loc[i, 'p2_result'] = wrap(h1.loc[i, 'poules'], 3)[1].split('/')[0]  # resultado
            h1.loc[i, 'p2_td'] = wrap(h1.loc[i, 'poules'], 3)[1].split('/')[1]  # dados
            h1.loc[i, 'p2_tr'] = wrap(h1.loc[i - 1, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 2)].split('/')[1]  # recibidos
            h1.loc[i, 'p2_opp'] = h1.loc[i - 1, 'id']  # rival

            # combate 3
            h1.loc[i, 'p3_result'] = wrap(h1.loc[i, 'poules'], 3)[2].split('/')[0]  # resultado
            h1.loc[i, 'p3_td'] = wrap(h1.loc[i, 'poules'], 3)[2].split('/')[1]  # dados
            h1.loc[i, 'p3_tr'] = wrap(h1.loc[i + 1, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 1)].split('/')[1]  # recibidos
            h1.loc[i, 'p3_opp'] = h1.loc[i + 1, 'id']  # rival

            # combate 4
            h1.loc[i, 'p4_result'] = wrap(h1.loc[i, 'poules'], 3)[0].split('/')[0]  # resultado
            h1.loc[i, 'p4_td'] = wrap(h1.loc[i, 'poules'], 3)[0].split('/')[1]  # dados
            h1.loc[i, 'p4_tr'] = wrap(h1.loc[i - 2, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 2)].split('/')[1]  # recibidos
            h1.loc[i, 'p4_opp'] = h1.loc[i - 2, 'id']  # rival

            # combate 5
            h1.loc[i, 'p5_result'] = wrap(h1.loc[i, 'poules'], 3)[3].split('/')[0]  # resultado
            h1.loc[i, 'p5_td'] = wrap(h1.loc[i, 'poules'], 3)[3].split('/')[1]  # dados
            h1.loc[i, 'p5_tr'] = wrap(h1.loc[i + 2, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 1)].split('/')[1]  # recibidos
            h1.loc[i, 'p5_opp'] = h1.loc[i + 2, 'id']  # rival

            # combate 6
            h1.loc[i, 'p6_result'] = wrap(h1.loc[i, 'poules'], 3)[5].split('/')[0]  # resultado
            h1.loc[i, 'p6_td'] = wrap(h1.loc[i, 'poules'], 3)[5].split('/')[1]  # dados
            h1.loc[i, 'p6_tr'] = wrap(h1.loc[i + 4, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 1)].split('/')[1]  # recibidos
            h1.loc[i, 'p6_opp'] = h1.loc[i + 4, 'id']  # rival

        elif h1.loc[i, 'poule_order'] == 4 and h1.loc[i, 'p_matches'] == 6:  # fourth seed in poule

            # combate 1
            h1.loc[i, 'p1_result'] = wrap(h1.loc[i, 'poules'], 3)[0].split('/')[
                0]  # resultado del combate (victoria o derrota (V - D)
            h1.loc[i, 'p1_td'] = wrap(h1.loc[i, 'poules'], 3)[0].split('/')[1]  # Toques Dados en el combate
            h1.loc[i, 'p1_tr'] = wrap(h1.loc[i - 3, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 2)].split('/')[
                1]  # Toques Recibidos en el combate
            h1.loc[i, 'p1_opp'] = h1.loc[i - 3, 'id']  # oponente del combate

            # combate 2
            h1.loc[i, 'p2_result'] = wrap(h1.loc[i, 'poules'], 3)[3].split('/')[0]  # resultado
            h1.loc[i, 'p2_td'] = wrap(h1.loc[i, 'poules'], 3)[3].split('/')[1]  # dados
            h1.loc[i, 'p2_tr'] = wrap(h1.loc[i + 1, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 1)].split('/')[1]  # recibidos
            h1.loc[i, 'p2_opp'] = h1.loc[i + 1, 'id']  # rival

            # combate 3
            h1.loc[i, 'p3_result'] = wrap(h1.loc[i, 'poules'], 3)[2].split('/')[0]  # resultado
            h1.loc[i, 'p3_td'] = wrap(h1.loc[i, 'poules'], 3)[2].split('/')[1]  # dados
            h1.loc[i, 'p3_tr'] = wrap(h1.loc[i - 1, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 2)].split('/')[1]  # recibidos
            h1.loc[i, 'p3_opp'] = h1.loc[i - 1, 'id']  # rival

            # combate 4
            h1.loc[i, 'p4_result'] = wrap(h1.loc[i, 'poules'], 3)[4].split('/')[0]  # resultado
            h1.loc[i, 'p4_td'] = wrap(h1.loc[i, 'poules'], 3)[4].split('/')[1]  # dados
            h1.loc[i, 'p4_tr'] = wrap(h1.loc[i + 2, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 1)].split('/')[1]  # recibidos
            h1.loc[i, 'p4_opp'] = h1.loc[i + 2, 'id']  # rival

            # combate 5
            h1.loc[i, 'p5_result'] = wrap(h1.loc[i, 'poules'], 3)[1].split('/')[0]  # resultado
            h1.loc[i, 'p5_td'] = wrap(h1.loc[i, 'poules'], 3)[1].split('/')[1]  # dados
            h1.loc[i, 'p5_tr'] = wrap(h1.loc[i - 2, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 2)].split('/')[1]  # recibidos
            h1.loc[i, 'p5_opp'] = h1.loc[i - 2, 'id']  # rival

            # combate 6
            h1.loc[i, 'p6_result'] = wrap(h1.loc[i, 'poules'], 3)[5].split('/')[0]  # resultado
            h1.loc[i, 'p6_td'] = wrap(h1.loc[i, 'poules'], 3)[5].split('/')[1]  # dados
            h1.loc[i, 'p6_tr'] = wrap(h1.loc[i + 3, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 1)].split('/')[1]  # recibidos
            h1.loc[i, 'p6_opp'] = h1.loc[i + 3, 'id']  # rival

        elif h1.loc[i, 'poule_order'] == 5 and h1.loc[i, 'p_matches'] == 6:  # fifth seed in poule

            # combate 1
            h1.loc[i, 'p1_result'] = wrap(h1.loc[i, 'poules'], 3)[1].split('/')[
                0]  # resultado del combate (victoria o derrota (V - D)
            h1.loc[i, 'p1_td'] = wrap(h1.loc[i, 'poules'], 3)[1].split('/')[1]  # Toques Dados en el combate
            h1.loc[i, 'p1_tr'] = wrap(h1.loc[i - 3, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 2)].split('/')[
                1]  # Toques Recibidos en el combate
            h1.loc[i, 'p1_opp'] = h1.loc[i - 3, 'id']  # oponente del combate

            # combate 2
            h1.loc[i, 'p2_result'] = wrap(h1.loc[i, 'poules'], 3)[3].split('/')[0]  # resultado
            h1.loc[i, 'p2_td'] = wrap(h1.loc[i, 'poules'], 3)[3].split('/')[1]  # dados
            h1.loc[i, 'p2_tr'] = wrap(h1.loc[i - 1, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 2)].split('/')[1]  # recibidos
            h1.loc[i, 'p2_opp'] = h1.loc[i - 1, 'id']  # rival

            # combate 3
            h1.loc[i, 'p3_result'] = wrap(h1.loc[i, 'poules'], 3)[0].split('/')[0]  # resultado
            h1.loc[i, 'p3_td'] = wrap(h1.loc[i, 'poules'], 3)[0].split('/')[1]  # dados
            h1.loc[i, 'p3_tr'] = wrap(h1.loc[i - 4, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 2)].split('/')[1]  # recibidos
            h1.loc[i, 'p3_opp'] = h1.loc[i - 4, 'id']  # rival

            # combate 4
            h1.loc[i, 'p4_result'] = wrap(h1.loc[i, 'poules'], 3)[5].split('/')[0]  # resultado
            h1.loc[i, 'p4_td'] = wrap(h1.loc[i, 'poules'], 3)[5].split('/')[1]  # dados
            h1.loc[i, 'p4_tr'] = wrap(h1.loc[i + 2, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 1)].split('/')[1]  # recibidos
            h1.loc[i, 'p4_opp'] = h1.loc[i + 2, 'id']  # rival

            # combate 5
            h1.loc[i, 'p5_result'] = wrap(h1.loc[i, 'poules'], 3)[2].split('/')[0]  # resultado
            h1.loc[i, 'p5_td'] = wrap(h1.loc[i, 'poules'], 3)[2].split('/')[1]  # dados
            h1.loc[i, 'p5_tr'] = wrap(h1.loc[i - 2, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 2)].split('/')[1]  # recibidos
            h1.loc[i, 'p5_opp'] = h1.loc[i - 2, 'id']  # rival

            # combate 6
            h1.loc[i, 'p6_result'] = wrap(h1.loc[i, 'poules'], 3)[4].split('/')[0]  # resultado
            h1.loc[i, 'p6_td'] = wrap(h1.loc[i, 'poules'], 3)[4].split('/')[1]  # dados
            h1.loc[i, 'p6_tr'] = wrap(h1.loc[i + 1, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 1)].split('/')[1]  # recibidos
            h1.loc[i, 'p6_opp'] = h1.loc[i + 1, 'id']  # rival

        elif h1.loc[i, 'poule_order'] == 6 and h1.loc[i, 'p_matches'] == 6:  # sixth seed in poule

            # combate 1
            h1.loc[i, 'p1_result'] = wrap(h1.loc[i, 'poules'], 3)[2].split('/')[
                0]  # resultado del combate (victoria o derrota (V - D)
            h1.loc[i, 'p1_td'] = wrap(h1.loc[i, 'poules'], 3)[2].split('/')[1]  # Toques Dados en el combate
            h1.loc[i, 'p1_tr'] = wrap(h1.loc[i - 3, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 2)].split('/')[
                1]  # Toques Recibidos en el combate
            h1.loc[i, 'p1_opp'] = h1.loc[i - 3, 'id']  # oponente del combate

            # combate 2
            h1.loc[i, 'p2_result'] = wrap(h1.loc[i, 'poules'], 3)[5].split('/')[0]  # resultado
            h1.loc[i, 'p2_td'] = wrap(h1.loc[i, 'poules'], 3)[5].split('/')[1]  # dados
            h1.loc[i, 'p2_tr'] = wrap(h1.loc[i + 1, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 1)].split('/')[1]  # recibidos
            h1.loc[i, 'p2_opp'] = h1.loc[i + 1, 'id']  # rival

            # combate 3
            h1.loc[i, 'p3_result'] = wrap(h1.loc[i, 'poules'], 3)[1].split('/')[0]  # resultado
            h1.loc[i, 'p3_td'] = wrap(h1.loc[i, 'poules'], 3)[1].split('/')[1]  # dados
            h1.loc[i, 'p3_tr'] = wrap(h1.loc[i - 4, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 2)].split('/')[1]  # recibidos
            h1.loc[i, 'p3_opp'] = h1.loc[i - 4, 'id']  # rival

            # combate 4
            h1.loc[i, 'p4_result'] = wrap(h1.loc[i, 'poules'], 3)[3].split('/')[0]  # resultado
            h1.loc[i, 'p4_td'] = wrap(h1.loc[i, 'poules'], 3)[3].split('/')[1]  # dados
            h1.loc[i, 'p4_tr'] = wrap(h1.loc[i - 2, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 2)].split('/')[1]  # recibidos
            h1.loc[i, 'p4_opp'] = h1.loc[i - 2, 'id']  # rival

            # combate 5
            h1.loc[i, 'p5_result'] = wrap(h1.loc[i, 'poules'], 3)[0].split('/')[0]  # resultado
            h1.loc[i, 'p5_td'] = wrap(h1.loc[i, 'poules'], 3)[0].split('/')[1]  # dados
            h1.loc[i, 'p5_tr'] = wrap(h1.loc[i - 5, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 2)].split('/')[1]  # recibidos
            h1.loc[i, 'p5_opp'] = h1.loc[i - 5, 'id']  # rival

            # combate 6
            h1.loc[i, 'p6_result'] = wrap(h1.loc[i, 'poules'], 3)[4].split('/')[0]  # resultado
            h1.loc[i, 'p6_td'] = wrap(h1.loc[i, 'poules'], 3)[4].split('/')[1]  # dados
            h1.loc[i, 'p6_tr'] = wrap(h1.loc[i + 1, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 1)].split('/')[1]  # recibidos
            h1.loc[i, 'p6_opp'] = h1.loc[i + 1, 'id']  # rival

        elif h1.loc[i, 'poule_order'] == 7 and h1.loc[i, 'p_matches'] == 6:  # seventh seed in poule

            # combate 1
            h1.loc[i, 'p1_result'] = wrap(h1.loc[i, 'poules'], 3)[0].split('/')[
                0]  # resultado del combate (victoria o derrota (V - D)
            h1.loc[i, 'p1_td'] = wrap(h1.loc[i, 'poules'], 3)[0].split('/')[1]  # Toques Dados en el combate
            h1.loc[i, 'p1_tr'] = wrap(h1.loc[i - 6, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 2)].split('/')[
                1]  # Toques Recibidos en el combate
            h1.loc[i, 'p1_opp'] = h1.loc[i - 6, 'id']  # oponente del combate

            # combate 2
            h1.loc[i, 'p2_result'] = wrap(h1.loc[i, 'poules'], 3)[5].split('/')[0]  # resultado
            h1.loc[i, 'p2_td'] = wrap(h1.loc[i, 'poules'], 3)[5].split('/')[1]  # dados
            h1.loc[i, 'p2_tr'] = wrap(h1.loc[i - 1, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 2)].split('/')[1]  # recibidos
            h1.loc[i, 'p2_opp'] = h1.loc[i - 1, 'id']  # rival

            # combate 3
            h1.loc[i, 'p3_result'] = wrap(h1.loc[i, 'poules'], 3)[4].split('/')[0]  # resultado
            h1.loc[i, 'p3_td'] = wrap(h1.loc[i, 'poules'], 3)[4].split('/')[1]  # dados
            h1.loc[i, 'p3_tr'] = wrap(h1.loc[i - 2, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 2)].split('/')[1]  # recibidos
            h1.loc[i, 'p3_opp'] = h1.loc[i - 2, 'id']  # rival

            # combate 4
            h1.loc[i, 'p4_result'] = wrap(h1.loc[i, 'poules'], 3)[1].split('/')[0]  # resultado
            h1.loc[i, 'p4_td'] = wrap(h1.loc[i, 'poules'], 3)[1].split('/')[1]  # dados
            h1.loc[i, 'p4_tr'] = wrap(h1.loc[i - 5, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 2)].split('/')[1]  # recibidos
            h1.loc[i, 'p4_opp'] = h1.loc[i - 5, 'id']  # rival

            # combate 5
            h1.loc[i, 'p5_result'] = wrap(h1.loc[i, 'poules'], 3)[3].split('/')[0]  # resultado
            h1.loc[i, 'p5_td'] = wrap(h1.loc[i, 'poules'], 3)[3].split('/')[1]  # dados
            h1.loc[i, 'p5_tr'] = wrap(h1.loc[i - 4, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 2)].split('/')[1]  # recibidos
            h1.loc[i, 'p5_opp'] = h1.loc[i - 4, 'id']  # rival

            # combate 6
            h1.loc[i, 'p6_result'] = wrap(h1.loc[i, 'poules'], 3)[3].split('/')[0]  # resultado
            h1.loc[i, 'p6_td'] = wrap(h1.loc[i, 'poules'], 3)[3].split('/')[1]  # dados
            h1.loc[i, 'p6_tr'] = wrap(h1.loc[i - 3, 'poules'], 3)[(h1.loc[i, 'poule_order'] - 2)].split('/')[1]  # recibidos
            h1.loc[i, 'p6_opp'] = h1.loc[i - 3, 'id']  # rival

    h1.drop(axis=1, columns=['index', 'name', 'n', 'poules', 'poullen'], inplace=True)

    ####################################################################################################################
    ############################################## organizando resultados de la poule ##################################

    h2['id'] = 'a'
    for i in range(len(h2)):
        h2['id'][i] = h2['Nombre'][i].replace(' ', '')[:11].lower()
    h2.rename(columns={'Rk.': 'rank_poule', 'TD': 'td_polues', 'TR': 'tr_poules', 'V': 'poule_vict', 'Diff.': 'p_diff',
                       'Ind.': 'poule_ind'}, inplace=True)
    h2.drop(axis=1, columns=['Nombre', 'Nation', 'Q', 'Edad'], inplace=True)

    ########################################## organizando datos tablas preliminares ###################################
    data = []

    if h3.empty:
        h3 = h3
    else:
        if h3.columns[0] == 'Table of 256':
            tp256 = h3[0:(list(h3[(h3.columns[0])]).index('Table of 128'))]
            tp256['pre256'] = 'pre256'
            data.append(tp256)
        if 'Table of 128' in list(h3[(h3.columns[0])]):
            tp128 = h3[(list(h3[(h3.columns[0])]).index('Table of 128')) + 1:(list(h3[(h3.columns[0])]).index(
                'Table of 128')) + 385]
            tp128['pre128'] = 'pre128'
            data.append(tp128)
        if h3.columns[0] == 'Table of 128':
            tp128 = h3[0:(list(h3[(h3.columns[0])]).index('Table of 64'))]
            tp128['pre128'] = 'pre128'
            data.append(tp128)
        if 'Table of 64' in list(h3[(h3.columns[0])]):
            tp64 = h3[(list(h3[(h3.columns[0])]).index('Table of 64')) + 1:]
            tp64['pre64'] = 'pre64'
            data.append(tp64)
        if h3.columns[0] == 'Table of 64':
            tp64 = h3[0:]
            tp64['pre64'] = 'pre64'
            data.append(tp64)

        for df in data:
            if 'BYE' in list(df[df.columns[0]]):
                for i in range(len(df)):
                    if df.loc[i, (df.columns[0])] == 'BYE':
                        df.loc[i, (df.columns[0])] = float('nan')
                        df.loc[i - 1, (df.columns[0])] = float('nan')
                        df.loc[i - 2, (df.columns[0])] = float('nan')
                df.dropna(axis=0, how='any', inplace=True)

    ###################################################### procesando todas las tablas ########################################
    if h4.columns[0] == 'Table of 256':
        t256 = h4[0:(list(h4[(h4.columns[0])]).index('Table of 128'))]
        t256['t256'] = 't256'
        data.append(t256)
    if 'Table of 128' in list(h4[(h4.columns[0])]):
        t128 = h4[(list(h4[(h4.columns[0])]).index('Table of 128')) + 1:(list(h4[(h4.columns[0])]).index('Table of 64'))]
        t128['t128'] = 't128'
        data.append(t128)
    if h4.columns[0] == 'Table of 128':
        t128 = h4[0:(list(h4[(h4.columns[0])]).index('Table of 64'))]
        t128['t128'] = 't128'
        data.append(t128)
    if 'Table of 64' in list(h4[(h4.columns[0])]):
        t64 = h4[(list(h4[(h4.columns[0])]).index('Table of 64')) + 1:(list(h4[(h4.columns[0])]).index('Table of 32'))]
        t64['t64'] = 't64'
        data.append(t64)
    if h4.columns[0] == 'Table of 64':
        t64 = h4[0:(list(h4[(h4.columns[0])]).index('Table of 32'))]
        t64['t64'] = 't4'
        data.append(t64)
    if 'Table of 32' in list(h4[(h4.columns[0])]):
        t32 = h4[(list(h4[(h4.columns[0])]).index('Table of 32')) + 1:(list(h4[(h4.columns[0])]).index('Table of 16'))]
        t32['t32'] = 't32'
        data.append(t32)
    if h4.columns[0] == 'Table of 32':
        t32 = h4[0:(list(h4[(h4.columns[0])]).index('Table of 16'))]
        t32['t32'] = 't32'
        data.append(t32)
    if 'Table of 16' in list(h4[(h4.columns[0])]):
        t16 = h4[(list(h4[(h4.columns[0])]).index('Table of 16')) + 1:]
        t16['t16'] = 't16'
        data.append(t16)
    if h4.columns[0] == 'Table of 16':
        t16 = h4[0:]
        t16['t16'] = 't16'
        data.append(t16)

    for df in data:
        if 'BYE' in list(df[df.columns[0]]):
            for i in range(len(df)):
                if df.loc[i, (df.columns[0])] == 'BYE':
                    df.loc[i, (df.columns[0])] = float('nan')
                    df.loc[i - 1, (df.columns[0])] = float('nan')
                    df.loc[i - 2, (df.columns[0])] = float('nan')
            df.dropna(axis=0, how='any', inplace=True)

    t8 = h5[0:24]
    t8['t8'] = 't8'
    semi = h5[25:37]
    semi['semi'] = 'semi'
    final = h5[38:]
    final['final'] = 'final'

    data.append(t8)
    data.append(semi)
    data.append(final)

    for df in data:
        df.rename(columns={df.columns[0]: 'ronda'}, inplace=True)
        df.reset_index(inplace=True)
        df['orden'] = (np.arange(0, (len(df))) + 1) % 3
        for i in range(len(df) - 2):
            df.loc[i, 'name'] = df.loc[i, 'ronda']
            df.loc[i, 'td'] = df.loc[i + 2, 'ronda']

        df.drop(df[df['orden'] != 1].index, inplace=True)
        df.reset_index(inplace=True)
        df['orden'] = (np.arange(0, (len(df))) + 1) % 2
        df['id'] = 'a'
        for i in range(len(df)):
            df['id'][i] = df['name'][i].replace(' ', '')[:11].lower()
        for i in range(len(df)):
            if df.loc[i, 'orden'] == 1:
                df.loc[i, 'td_' + df.columns[3]] = df.loc[i, 'td']  # Toques Dados en el combate
                df.loc[i, 'tr_' + df.columns[3]] = df.loc[i + 1, 'td']  # Toques Recibidos en el combate
                df.loc[i, 'opp_' + df.columns[3]] = df.loc[i + 1, 'id']  # oponente del combate
            elif df.loc[i, 'orden'] == 0:
                df.loc[i, 'td_' + df.columns[3]] = df.loc[i, 'td']  # Toques Dados en el combate
                df.loc[i, 'tr_' + df.columns[3]] = df.loc[i - 1, 'td']  # Toques Recibidos en el combate
                df.loc[i, 'opp_' + df.columns[3]] = df.loc[i - 1, 'id']  # oponente del combate

        df['match_dif_' + df.columns[3]] = df['td_' + df.columns[3]] - df['tr_' + df.columns[3]]
        for i in range(len(df)):
            if df.loc[i, 'match_dif_' + df.columns[3]] > 0:
                df.loc[i, 'match_res_' + df.columns[3]] = 'V'
            else:
                df.loc[i, 'match_res_' + df.columns[3]] = 'D'

        df.drop(axis=1, columns=['level_0', 'index', 'ronda', 'orden', 'name', 'td', df.columns[3]], inplace=True)

    ##################################################################################################################
    ################################################# resultados finales #############################################

    h6['id'] = 'a'
    for i in range(len(h6)):
        h6['id'][i] = h6['Nombre'][i].replace(' ', '')[:11].lower()
    h6.rename(columns={'Posición': 'final_pos', 'Edad': 'age', 'Puntos': 'points',
                       'Nombre': 'name', 'Nacionalidad': 'country'}, inplace=True)

    h6['competition'] = ' '.join(info.columns[0].split(' ')[:-7])
    h6['place'] = info.columns[0].split(' ')[-7]
    h6['date'] = pd.to_datetime(info.columns[0].split(' ')[-6], infer_datetime_format=True)
    h6['category'] = info.columns[0].split(' ')[-5]
    h6['weapon'] = info.columns[0].split(' ')[-4]
    h6['gender'] = info.columns[0].split(' ')[-3]
    h6['event'] = info.columns[0].split(' ')[-2]
    h6['type'] = info.columns[0].split(' ')[-1]
    ############################################## merging results1 ###################################################


    comp = functools.reduce(lambda left,right: pd.merge(left,right,on=['id'],how='outer'),data)#.fillna(' ')
    comp = pd.merge(left=h6,right=comp,on='id',how='outer')
    comp = pd.merge(left=comp,right=h2,on='id',how='outer')
    comp = pd.merge(left=comp,right=h1,on='id',how='outer')

    return comp



