# pocket-watch
Command-line script that lists datasets on a CKAN instance that are overdue for updates.

This repo now includes watchdog.py, which updates CKAN dataset parameters to show the true temporal coverage of the monitored tables in the dataset. pocket-watch uses the measured temporal coverage as a better check for data freshness.

## Sample output

```
> python glance.py

City of Pittsburgh Facilities is not considered stale because its data change rate is As Needed
City of Pittsburgh Playing Fields is not considered stale because its data change rate is As Needed
City of Pittsburgh Retaining Walls is not considered stale because its data change rate is As Needed
Waste Recovery Locations is not considered stale because its data change rate is As Needed
City of Pittsburgh Bridges is not considered stale because its data change rate is As Needed
City of Pittsburgh Signalized Intersections is not considered stale because its data change rate is As Needed
City of Pittsburgh Pools is not considered stale because its data change rate is As Needed
City of Pittsburgh Courts and Rinks is not considered stale because its data change rate is As Needed
City of Pittsburgh Playgrounds is not considered stale because its data change rate is As Needed
City of Pittsburgh Crosswalks is not considered stale because its data change rate is As Needed
City Traffic Signs is not considered stale because its data change rate is As Needed
Bike Rack Locations Downtown Pittsburgh is not considered stale because its data change rate is As Needed
Port Authority of Allegheny County Park and Rides is not considered stale because its data change rate is As Needed
Snow Plow Activity (2015-2016) is not considered stale because its data change rate is As Needed

Datasets by Staleness:
                                    Cycles  metadata_   publishing                           Upload
Title                                 late  modified    frequency    Publisher               Method
======================================================================================================
Current Bike Availability by S    21484.85  2016-11-21  Multiple Tim Healthy Ride            manual
Allegheny County Property View      843.76  2015-10-21  Daily        Allegheny County        manual
WPRDC Statistics                     32.73  2018-01-09  Daily        Western Pennsylvania Re etl
Police Community Outreach            14.71  2016-10-13  Monthly      City of Pittsburgh      manual
Baldwin Borough Monthly Revenu       12.51  2016-12-20  Monthly      Baldwin Borough         manual
Police Civil Actions                  4.29  2016-10-13  Quarterly    City of Pittsburgh      manual
Port Authority of Allegheny Co        3.89  2016-11-19  Quarterly    Port Authority of Alleg manual
Port Authority of Allegheny Co        3.89  2016-11-19  Quarterly    Port Authority of Alleg manual
Healthy Ride Stations                 2.19  2017-04-24  Quarterly    Healthy Ride            manual
ACED Allegheny Home Improvemen        1.09  2017-01-25  Bi-Annually  Allegheny County        manual
Pittsburgh International Airpo        0.86  2017-12-16  Monthly      Allegheny County Airpor manual
Parcel Centroids in Allegheny         0.76  2017-03-27  Bi-Annually  University of Pittsburg manual
Westmoreland County Crash Data        0.44  2016-09-01  Annually     Allegheny County        manual
Washington County Crash Data          0.44  2016-09-01  Annually     Allegheny County        manual
Butler County Crash Data              0.44  2016-09-01  Annually     Allegheny County        manual
Beaver County Crash Data              0.44  2016-09-01  Annually     Allegheny County        manual
Officer Training                      0.33  2016-10-13  Annually     City of Pittsburgh      manual
2011-2015 City of Pittsburgh O        0.20  2016-11-29  Annually     City of Pittsburgh      manual
Allegheny County Restaurant/Fo        0.09  2018-01-09  Monthly      Allegheny County        etl
Envision Downtown: Public Spac        0.01  2017-02-06  Annually     Envision Downtown       manual
======================================================================================================



Stale Datasets by Refresh-by Date:
                                    Cycles  metadata_   publishing                           Upload
Title                                 late  modified    frequency    Publisher               Method
======================================================================================================
Allegheny County Property View      843.76  2015-10-21  Daily        Allegheny County        manual
Westmoreland County Crash Data        0.44  2016-09-01  Annually     Allegheny County        manual
Washington County Crash Data          0.44  2016-09-01  Annually     Allegheny County        manual
Butler County Crash Data              0.44  2016-09-01  Annually     Allegheny County        manual
Beaver County Crash Data              0.44  2016-09-01  Annually     Allegheny County        manual
Officer Training                      0.33  2016-10-13  Annually     City of Pittsburgh      manual
Police Civil Actions                  4.29  2016-10-13  Quarterly    City of Pittsburgh      manual
Police Community Outreach            14.71  2016-10-13  Monthly      City of Pittsburgh      manual
Port Authority of Allegheny Co        3.89  2016-11-19  Quarterly    Port Authority of Alleg manual
Port Authority of Allegheny Co        3.89  2016-11-19  Quarterly    Port Authority of Alleg manual
Current Bike Availability by S    21484.85  2016-11-21  Multiple Tim Healthy Ride            manual
2011-2015 City of Pittsburgh O        0.20  2016-11-29  Annually     City of Pittsburgh      manual
Baldwin Borough Monthly Revenu       12.51  2016-12-20  Monthly      Baldwin Borough         manual
ACED Allegheny Home Improvemen        1.09  2017-01-25  Bi-Annually  Allegheny County        manual
Envision Downtown: Public Spac        0.01  2017-02-06  Annually     Envision Downtown       manual
Parcel Centroids in Allegheny         0.76  2017-03-27  Bi-Annually  University of Pittsburg manual
Healthy Ride Stations                 2.19  2017-04-24  Quarterly    Healthy Ride            manual
Pittsburgh International Airpo        0.86  2017-12-16  Monthly      Allegheny County Airpor manual
WPRDC Statistics                     32.73  2018-01-09  Daily        Western Pennsylvania Re etl
Allegheny County Restaurant/Fo        0.09  2018-01-09  Monthly      Allegheny County        etl
======================================================================================================

Out of 263 packages, only 150 have specified publication frequencies.
20 are stale (past their refresh-by date), according to the
metadata_modified field.
```

By defalt this script will try to send Slack alerts. To suppress this behavior, specify the `mute_alerts` value as a command-line parameter:
```
> python glance.py mute_alerts
```
