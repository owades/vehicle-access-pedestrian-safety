import pandas
import geopandas
from bokeh.models import GeoJSONDataSource, LinearColorMapper, CategoricalColorMapper, GMapOptions, ColorBar, ColumnDataSource, HoverTool, Label
from bokeh.plotting import figure, gmap, output_file, show
from bokeh.io import output_notebook, show, output_file
from bokeh.palettes import Blues9, Cividis256
from bokeh.transform import linear_cmap
from bokeh.layouts import row
import os
from shapely.geometry import shape, Point

# only needed if we're using gmaps API:
# from dotenv import load_dotenv
# load_dotenv()

###################################################
####### Import & process census survey data #######
###################################################

# data via https://data.census.gov/cedsci/table?q=dp04&t=Housing&g=0500000US06001.140000&tid=ACSDP5Y2019.DP04&moe=true&tp=true&hidePreview=true
census_data = pandas.read_csv('ACSDP5Y2019.DP04_2021-01-25T142900/ACSDP5Y2019.DP04_data_with_overlays_2021-01-25T142840.csv')

# filter data
census_data = census_data[[
							'id',
							'Geographic Area Name',
							'Estimate!!VEHICLES AVAILABLE!!Occupied housing units!!No vehicles available',
							'Percent!!VEHICLES AVAILABLE!!Occupied housing units!!No vehicles available',
							'Estimate!!VEHICLES AVAILABLE!!Occupied housing units!!1 vehicle available',
							'Percent!!VEHICLES AVAILABLE!!Occupied housing units!!1 vehicle available',
							'Estimate!!VEHICLES AVAILABLE!!Occupied housing units!!2 vehicles available',
							'Percent!!VEHICLES AVAILABLE!!Occupied housing units!!2 vehicles available',
							'Estimate!!VEHICLES AVAILABLE!!Occupied housing units!!3 or more vehicles available',
							'Percent!!VEHICLES AVAILABLE!!Occupied housing units!!3 or more vehicles available',
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

######################################################
####### Import & process census tract geo data #######
######################################################

# data API via: https://data.acgov.org/datasets/7b064a13a9234bfba97654007ccbf8e8_0
tracts = geopandas.read_file("https://opendata.arcgis.com/datasets/7b064a13a9234bfba97654007ccbf8e8_0.geojson")

# clean tract identifier
tracts['DIST_NAME'] = tracts['DIST_NAME'].str.replace('CENSUS TRACT #', '')
tracts.rename(columns={
					'DIST_NAME':'tract_num'
					}, inplace=True)

###########################################
####### Import & process crash data #######
###########################################

# CHP SWITRS/Berkeley TIMS data:  https://tims.berkeley.edu/tools/query/summary.php
# Filtered for ped-invovled, 2015-2019 (note that 2019 data may not be complete)
collisions = pandas.read_csv('Collisions.csv', low_memory=False)
collisions = collisions[collisions['POINT_Y'].notna()]
collisions = collisions[collisions['POINT_X'].notna()]
collisions = collisions[[
								'CASE_ID',
								'ACCIDENT_YEAR',
								'PROC_DATE',
								'COLLISION_DATE',
								'COLLISION_TIME',
								'COUNT_PED_KILLED',
								'COUNT_PED_INJURED',
								'COUNT_BICYCLIST_KILLED',
								'COUNT_BICYCLIST_INJURED',
								'POINT_Y',
								'POINT_X'
								]]

collisions_geo = geopandas.GeoDataFrame(
    collisions, geometry=geopandas.points_from_xy(collisions['POINT_X'], collisions['POINT_Y']), crs="EPSG:4326")

##################################################
####### Combine census, tract & crash data #######
##################################################

## Merge census survey data with tract geo data ##
census_tracts = tracts.merge(census_data, left_on='tract_num', right_on='tract_num')

# Map ped crashes with the census tract where the crash occurred
# ('spatial join' is very cool function - before I found it was trying to use a nested for loop...)
crashes_with_tracts = geopandas.sjoin(collisions_geo, census_tracts, how="inner")

# count how many crashes associated with each census tract:
tract_crash_counts = crashes_with_tracts['tract_num'].value_counts().rename_axis('tract_num').reset_index(name='crashes')

## Merge crash data into census tract data ##
census_tract_crashes = census_tracts.merge(tract_crash_counts, left_on='tract_num', right_on='tract_num', how='left')
census_tract_crashes['ped_crashes_per_1k_households'] = census_tract_crashes['crashes'] * 1000.0 / census_tract_crashes['total_housing_units']
census_tract_crashes['ped_crashes_per_1k_households'] = census_tract_crashes['ped_crashes_per_1k_households'].fillna(0)
census_tract_crashes['ped_crashes_per_1k_households'] = census_tract_crashes['ped_crashes_per_1k_households'].fillna(0)



################################
### Filter anomolous values ####
################################

# tracts with very few housing units are likely to have anomolous values, which throws off the color
# census_tract_crashes = census_tract_crashes.loc[census_tract_crashes['total_housing_units'] > 50]

#############################################################
### Create map of normalized pedestrian crashes by tract ####
#############################################################

mapper = linear_cmap(field_name='ped_crashes_per_1k_households', palette=Cividis256 ,low=census_tract_crashes['ped_crashes_per_1k_households'].min() ,high=50)
# mapper = linear_cmap(field_name='ped_crashes_per_1k_households', palette=Cividis256 ,low=census_tract_crashes['ped_crashes_per_1k_households'].min() ,high=census_tract_crashes['ped_crashes_per_1k_households'].max())

# in case we want gmap instead of blank figure, swap below 3 lines out for the figure() function:
# map_options = GMapOptions(lat=37.698882, lng=-122.115695, map_type="hybrid", zoom=11)
# API_KEY = os.getenv('GMAP_API_KEY')
# p = gmap(API_KEY, map_options,plot_width=500, plot_height=500) #creates our map!

p = figure(
			title="Alameda County: Vehicle Crashes Involving Pedestrians per 1k Households (2015-2019)",
			background_fill_color="white",
			toolbar_location=None,
			x_axis_type="mercator",
			y_axis_type="mercator",
			x_range=(-122.349, -122.126),
			y_range=(37.750, 37.910)
		)

p.yaxis.major_tick_line_color = None  # turn off y-axis major ticks
p.yaxis.minor_tick_line_color = None  # turn off y-axis minor ticks
p.xaxis.major_tick_line_color = None  # turn off y-axis major ticks
p.xaxis.minor_tick_line_color = None  # turn off y-axis minor ticks
p.xgrid.grid_line_color = None
p.ygrid.grid_line_color = None
p.xaxis.major_label_text_font_size = '0pt'  # turn off x-axis tick labels
p.yaxis.major_label_text_font_size = '0pt'  # turn off y-axis tick labels

geo_source = GeoJSONDataSource(geojson=census_tract_crashes.to_json()) #map will contain our census tract data
crash_geo_source = GeoJSONDataSource(geojson=collisions_geo.to_json()) #map will contain our census tract data

p.patches('xs', 'ys', fill_color =mapper, line_color='black', fill_alpha=0.8, source=geo_source) # creates "patches" (ie shapes) based on our geo data

# show red dots for each ped crash:
# p.circle(size=1, fill_color="red", fill_alpha=1, line_alpha=0, source=crash_geo_source)

color_bar = ColorBar(color_mapper=mapper['transform'], width=8,  location=(0,0))
p.add_layout(color_bar, 'left')

TOOLTIPS = [
    ('Tract Number', '@tract_num'),
	('Ped crashes per 1k households', '@ped_crashes_per_1k_households'),
	('Crashes with pedestrians', '@crashes'),
    ('Homes','@total_housing_units')
]

p.add_tools( HoverTool(tooltips=TOOLTIPS))

############################################
## Create map of car ownership by tract ####
############################################

mapper = linear_cmap(field_name='has_a_vehicle_percent', palette=list(reversed(Cividis256)) ,low=census_data['has_a_vehicle_percent'].min() ,high=census_data['has_a_vehicle_percent'].max())

# use list(reversed()) to flip a pallette:
# list(reversed(Blues9))

# map_options = GMapOptions(lat=37.698882, lng=-122.115695, map_type="hybrid", zoom=11)
# API_KEY = os.getenv('GMAP_API_KEY')
# q = gmap(API_KEY, map_options,plot_width=500, plot_height=500) #creates our map!

q = figure(
			title="Alameda County: Percent of Households with Access to 1 or more Cars (2019)",
			background_fill_color="white",
			toolbar_location=None,
			x_axis_type="mercator",
			y_axis_type="mercator",
			x_range=(-122.349, -122.126),
			y_range=(37.750, 37.910)
			)
# the projection is weird...maybe use a tile provider here instead: https://docs.bokeh.org/en/latest/docs/user_guide/geo.html

 
q.yaxis.major_tick_line_color = None  # turn off y-axis major ticks
q.yaxis.minor_tick_line_color = None  # turn off y-axis minor ticks
q.xaxis.major_tick_line_color = None  # turn off y-axis major ticks
q.xaxis.minor_tick_line_color = None  # turn off y-axis minor ticks
q.xgrid.grid_line_color = None
q.ygrid.grid_line_color = None
q.xaxis.major_label_text_font_size = '0pt'  # turn off x-axis tick labels
q.yaxis.major_label_text_font_size = '0pt'  # turn off y-axis tick labels

geo_source = GeoJSONDataSource(geojson=census_tracts.to_json()) #map will contain our census tract data

q.patches('xs', 'ys', fill_color =mapper, line_color='black', fill_alpha=0.8, source=geo_source) # creates "patches" (ie shapes) based on our geo data
color_bar = ColorBar(color_mapper=mapper['transform'], width=8, location=(0,0))
q.add_layout(color_bar, 'right')

TOOLTIPS = [
	('Tract Number', '@tract_num'),
    ('Has a vehicle percent', '@has_a_vehicle_percent'),
    ('Homes','@total_housing_units')
]

q.add_tools( HoverTool(tooltips=TOOLTIPS))


output_file('index.html', title='Alameda County Car Ownership vs Pedestrian Collisions')
show(row(p,q))