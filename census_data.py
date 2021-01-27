import pandas
import geopandas
from bokeh.models import GeoJSONDataSource, LinearColorMapper, CategoricalColorMapper, GMapOptions, ColorBar, ColumnDataSource, HoverTool
from bokeh.plotting import figure, gmap, output_file, show
from bokeh.io import output_notebook, show, output_file
from bokeh.palettes import Blues9, Cividis256
from bokeh.transform import linear_cmap
import os
from shapely.geometry import shape, Point
from dotenv import load_dotenv
load_dotenv()

####### Import & process census survey data #######
# data via https://data.census.gov/cedsci/table?q=dp04&t=Housing&g=0500000US06001.140000&tid=ACSDP5Y2019.DP04&moe=true&tp=true&hidePreview=true
census_data = pandas.read_csv('ACSDP5Y2019.DP04_2021-01-25T142900/ACSDP5Y2019.DP04_data_with_overlays_2021-01-25T142840.csv')

# filter data
census_data = census_data[[
							'id',
							'Geographic Area Name',
							'Estimate!!VEHICLES AVAILABLE!!Occupied housing units!!No vehicles available',
							# 'Margin of Error!!VEHICLES AVAILABLE!!Occupied housing units!!No vehicles available',
							'Percent!!VEHICLES AVAILABLE!!Occupied housing units!!No vehicles available',
							# 'Percent Margin of Error!!VEHICLES AVAILABLE!!Occupied housing units!!No vehicles available',
							'Estimate!!VEHICLES AVAILABLE!!Occupied housing units!!1 vehicle available',
							# 'Margin of Error!!VEHICLES AVAILABLE!!Occupied housing units!!1 vehicle available',
							'Percent!!VEHICLES AVAILABLE!!Occupied housing units!!1 vehicle available',
							# 'Percent Margin of Error!!VEHICLES AVAILABLE!!Occupied housing units!!1 vehicle available',
							'Estimate!!VEHICLES AVAILABLE!!Occupied housing units!!2 vehicles available',
							# 'Margin of Error!!VEHICLES AVAILABLE!!Occupied housing units!!2 vehicles available',
							'Percent!!VEHICLES AVAILABLE!!Occupied housing units!!2 vehicles available',
							# 'Percent Margin of Error!!VEHICLES AVAILABLE!!Occupied housing units!!2 vehicles available',
							'Estimate!!VEHICLES AVAILABLE!!Occupied housing units!!3 or more vehicles available',
							# 'Margin of Error!!VEHICLES AVAILABLE!!Occupied housing units!!3 or more vehicles available',
							'Percent!!VEHICLES AVAILABLE!!Occupied housing units!!3 or more vehicles available',
							# 'Percent Margin of Error!!VEHICLES AVAILABLE!!Occupied housing units!!3 or more vehicles available'
							'Estimate!!HOUSING OCCUPANCY!!Total housing units'
						]]

# clean tract identifier
census_data['Geographic Area Name'] = census_data['Geographic Area Name'].str.replace('Census Tract ', '')
census_data['Geographic Area Name'] = census_data['Geographic Area Name'].str.replace(', Alameda County, California', '')

census_data.rename(columns={
					'Geographic Area Name':'tract_num',
					'Estimate!!VEHICLES AVAILABLE!!Occupied housing units!!No vehicles available':'no_vehicles_count',
					'Estimate!!VEHICLES AVAILABLE!!Occupied housing units!!1 vehicle available':'1_vehicle_count',
					'Estimate!!VEHICLES AVAILABLE!!Occupied housing units!!2 vehicles available':'2_vehicles_count',
					'Estimate!!VEHICLES AVAILABLE!!Occupied housing units!!3 or more vehicles available':'3_or_more_vehicles_count',
					'Percent!!VEHICLES AVAILABLE!!Occupied housing units!!No vehicles available':'no_vehicles_percent',
					'Percent!!VEHICLES AVAILABLE!!Occupied housing units!!1 vehicle available':'1_vehicle_percent',
					'Percent!!VEHICLES AVAILABLE!!Occupied housing units!!2 vehicles available':'2_vehicles_percent',
					'Percent!!VEHICLES AVAILABLE!!Occupied housing units!!3 or more vehicles available':'3_or_more_vehicles_percent',
					'Estimate!!HOUSING OCCUPANCY!!Total housing units':'total_housing_units'
					}, inplace=True)

# null values were showing up as a '-'. This line would cause issues if there were '-' characters by design
census_data.replace({'-': None},inplace =True)

# they were defaulting to strings:
census_data = census_data.astype({
					'no_vehicles_percent': float, 
                	'1_vehicle_percent': float, 
                	'2_vehicles_percent': float, 
                	'3_or_more_vehicles_percent': float
               } )


# combine 1, 2, 3+ vehicles into 'has vehicle'
census_data['has_a_vehicle_count'] = census_data['1_vehicle_count'] + census_data['2_vehicles_count'] + census_data['3_or_more_vehicles_count']
census_data['has_a_vehicle_percent'] = census_data['1_vehicle_percent'] + census_data['2_vehicles_percent'] + census_data['3_or_more_vehicles_percent']

####### Import & process census tract geo data #######
# data API via: https://data.acgov.org/datasets/7b064a13a9234bfba97654007ccbf8e8_0
tracts = geopandas.read_file("https://opendata.arcgis.com/datasets/7b064a13a9234bfba97654007ccbf8e8_0.geojson")

# clean tract identifier
tracts['DIST_NAME'] = tracts['DIST_NAME'].str.replace('CENSUS TRACT #', '')
tracts.rename(columns={
					'DIST_NAME':'tract_num'
					}, inplace=True)

## Merge census survey data with tract geo data ##

census_tracts = tracts.merge(census_data, left_on='tract_num', right_on='tract_num')

# export to CSV for validation purposes:
# census_data.to_csv('census.csv',index=False,header=True)
# tracts.to_csv('tracts.csv',index=False,header=True)
# census_tracts.to_csv('census_tracts.csv',index=False,header=True)

####### Import & process crash data #######

# CHP SWITRS data: https://iswitrs.chp.ca.gov/Reports/jsp/CollisionReports.jsp
# more info about SWITRS program: https://www.chp.ca.gov/programs-services/services-information/switrs-internet-statewide-integrated-traffic-records-system

firsthalf_crashes = pandas.read_csv('CollisionRecords_firsthalf_19.csv', low_memory=False)
secondhalf_crashes = pandas.read_csv('CollisionRecords_secondhalf_19.csv', low_memory=False)

# combine firsthalf and secondhalf:
crashes_2019 = pandas.concat([firsthalf_crashes,secondhalf_crashes]).drop_duplicates().reset_index(drop=True)

crashes_2019 = crashes_2019[crashes_2019['LATITUDE'].notna()]
crashes_2019 = crashes_2019[crashes_2019['LONGITUDE'].notna()]

# for some reason the CHP data had positive longitude values. Thankfully they only have data for one hemisphere
crashes_2019['LONGITUDE'] *= -1

crashes_2019 = crashes_2019[[
								'CASE_ID',
								'ACCIDENT_YEAR',
								'PROC_DATE',
								'COLLISION_DATE',
								'COLLISION_TIME',
								'COUNT_PED_KILLED',
								'COUNT_PED_INJURED',
								'COUNT_BICYCLIST_KILLED',
								'COUNT_BICYCLIST_INJURED',
								'LATITUDE',
								'LONGITUDE'
								]]

# print (crashes_2019.dtypes)
crashes_2019 = crashes_2019.astype({
                	'CASE_ID': int,
					'ACCIDENT_YEAR': int,
					'PROC_DATE': int,
					'COLLISION_DATE': int,
					'COLLISION_TIME': int,
					'COUNT_PED_KILLED': int,
					'COUNT_PED_INJURED': int,
					'COUNT_BICYCLIST_KILLED': int,
					'COUNT_BICYCLIST_INJURED': int,
					'LATITUDE': float,
					'LONGITUDE': float
               	})

# remove data from 2020:
crashes_2019 = crashes_2019.loc[crashes_2019['COLLISION_DATE'] < 20200101]

crashes_2019_geo = geopandas.GeoDataFrame(
    crashes_2019, geometry=geopandas.points_from_xy(crashes_2019['LONGITUDE'], crashes_2019['LATITUDE']), crs="EPSG:4326")
# filter for ped-invovled:
ped_crashes_2019 = crashes_2019_geo.loc[crashes_2019['COUNT_PED_KILLED'] + crashes_2019['COUNT_PED_INJURED'] > 0]
# ped_crashes_2019_mini = ped_crashes_2019.head()


crashes_with_tracts = geopandas.sjoin(ped_crashes_2019, census_tracts, how="inner")
# crashes_with_census.to_csv('crashes_with_census.csv',index=False,header=True)

tract_crash_counts = crashes_with_tracts['tract_num'].value_counts().rename_axis('tract_num').reset_index(name='crashes')

# tract_crash_counts.to_csv('tract_crash_counts.csv',index=False,header=True)

## Merge crash data into census tract data ##
census_tract_crashes = census_tracts.merge(tract_crash_counts, left_on='tract_num', right_on='tract_num', how='left')
census_tract_crashes['ped_crashes_per_1k_households'] = census_tract_crashes['crashes'] * 1000.0 / census_tract_crashes['total_housing_units']
census_tract_crashes['ped_crashes_per_1k_households'] = census_tract_crashes['ped_crashes_per_1k_households'].fillna(0)
census_tract_crashes['ped_crashes_per_1k_households'] = census_tract_crashes['ped_crashes_per_1k_households'].fillna(0)

#temporary filter for anomolous value:
census_tract_crashes = census_tract_crashes.loc[census_tract_crashes['tract_num'] != '4226']

# census_tract_crashes.to_csv('census_tract_crashes.csv',index=False,header=True)

### Create map of normalized pedestrian crashes by tract ####:
print(census_tract_crashes['ped_crashes_per_1k_households'].min())
print(census_tract_crashes['ped_crashes_per_1k_households'].max())
mapper = linear_cmap(field_name='ped_crashes_per_1k_households', palette=list(reversed(Cividis256)) ,low=census_tract_crashes['ped_crashes_per_1k_households'].min() ,high=census_tract_crashes['ped_crashes_per_1k_households'].max())

# use list(reversed()) to flip a pallcensus_tract_crashesette:
# list(reversed(Blues9))

map_options = GMapOptions(lat=37.84, lng=-122.2835, map_type="hybrid", zoom=12)
API_KEY = os.getenv('GMAP_API_KEY')
p = gmap(API_KEY, map_options,plot_width=1000, plot_height=1000) #creates our map!

# p = figure(background_fill_color="white")
# the projection is weird...maybe use a tile provider here instead: https://docs.bokeh.org/en/latest/docs/user_guide/geo.html

p.yaxis.major_tick_line_color = None  # turn off y-axis major ticks
p.yaxis.minor_tick_line_color = None  # turn off y-axis minor ticks
p.xaxis.major_tick_line_color = None  # turn off y-axis major ticks
p.xaxis.minor_tick_line_color = None  # turn off y-axis minor ticks
p.xaxis.major_label_text_font_size = '0pt'  # turn off x-axis tick labels
p.yaxis.major_label_text_font_size = '0pt'  # turn off y-axis tick labels

geo_source = GeoJSONDataSource(geojson=census_tract_crashes.to_json()) #map will contain our census tract data

p.patches('xs', 'ys', fill_color =mapper, line_color='black', fill_alpha=0.8, source=geo_source) # creates "patches" (ie shapes) based on our geo data
color_bar = ColorBar(color_mapper=mapper['transform'], width=8,  location=(0,0))
p.add_layout(color_bar, 'right')

TOOLTIPS = [
    ('Tract Number', '@tract_num'),
	('Ped crashes per k households', '@ped_crashes_per_1k_households'),
    ('Homes','@total_housing_units')
]

p.add_tools( HoverTool(tooltips=TOOLTIPS))

show(p)

## Create map of car ownership by tract ####:

mapper = linear_cmap(field_name='has_a_vehicle_percent', palette=list(reversed(Cividis256)) ,low=census_data['has_a_vehicle_percent'].min() ,high=census_data['has_a_vehicle_percent'].max())

# use list(reversed()) to flip a pallcensus_tract_crashesette:
# list(reversed(Blues9))

map_options = GMapOptions(lat=37.84, lng=-122.2835, map_type="hybrid", zoom=12)
API_KEY = os.getenv('GMAP_API_KEY')
q = gmap(API_KEY, map_options,plot_width=1000, plot_height=1000) #creates our map!

# q = figure(background_fill_color="white")
# the projection is weird...maybe use a tile provider here instead: https://docs.bokeh.org/en/latest/docs/user_guide/geo.html

q.yaxis.major_tick_line_color = None  # turn off y-axis major ticks
q.yaxis.minor_tick_line_color = None  # turn off y-axis minor ticks
q.xaxis.major_tick_line_color = None  # turn off y-axis major ticks
q.xaxis.minor_tick_line_color = None  # turn off y-axis minor ticks
q.xaxis.major_label_text_font_size = '0pt'  # turn off x-axis tick labels
q.yaxis.major_label_text_font_size = '0pt'  # turn off y-axis tick labels

geo_source = GeoJSONDataSource(geojson=census_tracts.to_json()) #map will contain our census tract data

q.patches('xs', 'ys', fill_color =mapper, line_color='black', fill_alpha=0.8, source=geo_source) # creates "patches" (ie shapes) based on our geo data
color_bar = ColorBar(color_mapper=mapper['transform'], width=8,  location=(0,0))
q.add_layout(color_bar, 'right')

TOOLTIPS = [
    ('Has a vehicle percent', '@has_a_vehicle_percent'),
    ('Homes','@total_housing_units')
]

q.add_tools( HoverTool(tooltips=TOOLTIPS))

show(q)