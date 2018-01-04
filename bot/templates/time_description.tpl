<b>Command description:</b>
/time issue issue-key start-date end-date - returns a report of spend time of issue
/time user username start-date end-date - returns a report of spend time of user
/time project KEY start-date end-date - returns a report of spend time of project

<b>Note:</b>
1. End date is not required
2. As start date may be specified day: <i> today</i> or <i>yesterday</i>. In this case end date not required.
3. If the start date is specified - the command will be executed inclusively from the start date to today's date

<b>Examples:</b>
/time user username today
/time issue JTB-11 yesterday
/time project JTB 28/Dec/2017
/time user username 24-11-2017 29-11-2017