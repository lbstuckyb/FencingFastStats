# FencingFastStats

step by step

1. Upload competition results .csv file to comp_results folder
2. Run input_new_results.py with the new csv files
3. Once every new competition is loaded and added to the new_results.csv file RUN the update_data.py file
4. BEFORE RUNNING update_data.py
   1. Change the old data file name to the most recent csv file
   ```
   df = pd.read_csv('./final_results/XXXXXXX.csv')
   ```
   2. Change the output file name to the new date name

   ```
   final_df.to_csv('./data/XXXXXXX.csv')
   ```
6. RUN update_data.py
7. Add the new results file to the project to be included in the commit
8. Commit and Push to origin-master
9. Update heroku app with new results file