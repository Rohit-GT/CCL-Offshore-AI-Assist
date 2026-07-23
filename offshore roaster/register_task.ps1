# Define the action: execute the batch script via cmd.exe
$action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument '/c "c:\Users\CCL-04\ai_project\offshore roaster\run_sync_task.bat"'

# Define the trigger: Daily at 9:00 AM
$trigger = New-ScheduledTaskTrigger -Daily -At "9:00 AM"

# Configure settings: Allow task to start on battery, don't stop if it switches to battery
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

# Register the Scheduled Task (will overwrite if exists via -Force)
Register-ScheduledTask -TaskName "SyncShiftRoster" -Action $action -Trigger $trigger -Settings $settings -Description "Daily automatic sync of CCL Offshore Team Shift Roster from Excel to SQL Server" -Force

Write-Host "Scheduled task 'SyncShiftRoster' registered successfully. It will run daily at 9:00 AM."
