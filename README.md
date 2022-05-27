# FencingFastStats

step by step

1. Upload competition results .csv file to comp_results folder
2. Run input_new_results.py with the new csv files
3. Once every new comptetion is loaded and added to the new_results.csv file RUN the update_data.py file
4. BEFORE RUNNING update_data.py
   1. Change the old data file name to the most recent csv file
      1. df = pd.read_csv('./final_results/XXXXXXX.csv')
   2. Change the output file name to the new date name
      1. final_df.to_csv('./XXXXXXX.csv')
5. RUN update_data.py
6. Add the new results file to the project to be included in the commit
7. 