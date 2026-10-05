so we will get input as i text like 
""" 
works i have is 

hiwi i have to work for 8 hrs a week , can compansate with sat and sunday also
thesis main focus need to work a fixed time every day
job applying either morning or evening like night every day 1hr
upskill theory
upskilling project coding daily some
keep saturday free monday to friday and sunday
night 1hr german A1
"""

tables
1. Logentry
user id , 
queryid, 
time , 
saves the users real query as it is

2. Slot_raw
id
queryid, 
llm_slot_format -- ie we give this text to llm and llm will give back the text in a format
ex :{activity: hiwi time/per week : 8/no prescribed time mentioned,day_prefrence:on monday or weekdays/none rules: [not on sunday, only in morning slot]}

3. Activity form each query in the slot table #plan
  id, user_id,slotid
  name                 "Thesis", "HiWi", "German A1"
  weekly_target_min    1200 for thesis (20h), 480 for HiWi
  daypreference.        if any or none
  priority             1 = most important, used when deciding what gets freed time maybe as for this to user if not given
  locked               True for German and job apps: never moved by the engine

4. Slot
  id, user_id
  date, start, end
  activity_id
  status               planned | done | skipped | replaced
  source               "plan" (from the monthly plan) | "replan" (moved by the engine)

5. Rules
  free_days            [Saturday]
  week_starts_on       Monday
  day_window           08:00 to 22:00
  slot_step_min        15

6. ReplanProposal -- comes with #replane
  id, created_at
  changes              list of (slot_id, from_activity, to_activity)
  status               pending | approved | rejected


daily incase user do replanning we need to replan it and ask questions to user incase of dbts
let user tell wat to do
but dont as all questions
also tell the replan idea and let them approve then change