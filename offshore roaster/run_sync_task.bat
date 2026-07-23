@echo off
echo Starting Shift Roster Sync: %date% %time% >> "c:\Users\CCL-04\ai_project\offshore roaster\sync_log.txt"
python "c:\Users\CCL-04\ai_project\offshore roaster\sync_roster.py" >> "c:\Users\CCL-04\ai_project\offshore roaster\sync_log.txt" 2>&1
echo Sync process finished. >> "c:\Users\CCL-04\ai_project\offshore roaster\sync_log.txt"
echo ---------------------------------------- >> "c:\Users\CCL-04\ai_project\offshore roaster\sync_log.txt"
