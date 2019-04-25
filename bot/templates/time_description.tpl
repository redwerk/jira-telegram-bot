<b>Command description:</b>
/time <i>issue {issue-key} {start-date} {end-date}</i> - return a report of time spent on a certain issue
/time <i>user {username} {start-date} {end-date}</i> - return a report of time spent by a certain user
/time <i>project {project-key} {start-date} {end-date}</i> - returns a report of spend time of project

<b>Note:</b>
1. <i>{end date}</i> is optional
2. <i>{start-date}</i> may be specified as: <i>today</i> or <i>yesterday</i>. In this case end date is not required.
3. If <i>{start-date}</i> is specified, the command will be executed inclusively from the start date to today's date

<b>Examples:</b>
/time <i>user username today</i>
/time <i>issue JTB-11 yesterday</i>
/time <i>project JTB 28/Dec/2017</i>
/time <i>user username 24-11-2017 29-11-2017</i>
