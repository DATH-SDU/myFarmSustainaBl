"""

 Implementation of FarmSustainaBl modelling and simulation work package.
 Please refer to Readme file, to how to run this file. 
 
  @Drisya Alex Thumba, email: dath@mmmi.sd.dk, drisyavictoria@gmail.com 
  @This code is updated on Jan 2020 and tested with "Ubuntu 20.04.1 LTS" OS.
  @Version: On developing stage 
 """

try:
    import asyncio
except ImportError:
    raise RuntimeError("This example requries Python3 / asyncio")

from threading import Thread

from flask import Flask, render_template
from tornado.httpserver import HTTPServer
from tornado.ioloop import IOLoop

from bokeh.application import Application
from bokeh.application.handlers import FunctionHandler
from bokeh.embed import server_document
from bokeh.layouts import column, row
from bokeh.models import ColumnDataSource, Slider, Select
from bokeh.plotting import figure
from bokeh.sampledata.sea_surface_temperature import sea_surface_temperature
from bokeh.server.server import BaseServer
from bokeh.server.tornado import BokehTornado
from bokeh.server.util import bind_sockets
from bokeh.themes import Theme
from bokeh.layouts import gridplot
from math import pi
from bokeh.palettes import Category20c
from bokeh.transform import cumsum
from bokeh.models.widgets import DataTable, DateFormatter, TableColumn
from bokeh.palettes import Dark2_5 as palette
from bokeh.core.properties import value

import pandas as pd
from statistics import mean
import itertools

if __name__ == '__main__':
    print('This script is intended to be run with gunicorn. e.g.')
    print()
    print('    gunicorn -w 4 flask_gunicorn_embed:app')
    print()
    print('will start the app on four processes')
    import sys
    sys.exit()

app = Flask(__name__)

def bkapp(doc):
    ################# Data Preperation
    cattle = pd.read_csv("./cattle.csv",index_col=0)

    cattle = cattle.drop('t',axis=0)
    cattle = cattle.drop('s',axis=0)
    cattle = cattle.apply(pd.to_numeric)

    ################## GHG From Manure Calculation
    vs = (cattle.loc['ge']*(1-cattle.loc['de%']/100)+cattle.loc['ue_ge'])*((1-cattle.loc['ash'])/18.45)
    ef_t = (vs*365)*(cattle.loc['bot']*0.67*cattle.loc['mcf_sk']/100*cattle.loc['ms_tsk'])
    ch4manure = (ef_t*cattle.loc['n_t'])/pow(10,6)
    nex_t = cattle.loc['nrate_t']*cattle.loc['tam_t']/1000*365
    n2od_mm = ((cattle.loc['n_t']*nex_t*cattle.loc['ms_ts'])*cattle.loc['ef_3s'])*(44/28)
    nvolatilization_mms = cattle.loc['n_t']*nex_t*cattle.loc['ms_ts']*(cattle.loc['fracgas_ms']/100)
    n2og_mm = (nvolatilization_mms*cattle.loc['ef_4'])*(44/28)
    nleaching_mms = (cattle.loc['n_t']*nex_t*cattle.loc['ms_ts'])*(cattle.loc['fracleach_ms']/100)
    n2oĺ_mm = (nleaching_mms*cattle.loc['ef_5'])*(44/28)

    n2oid_mm = n2og_mm + n2oĺ_mm
    ghg_manure = n2oid_mm + ch4manure

    ###################### Farm Information Table
    farm_info_dict = {'variable':['Dairy Cattle', 'Manure Mangement System'],'info':[12,'Liquid Slurry']}
    farm_info_source = ColumnDataSource(data=farm_info_dict)
    farm_info_columns = [TableColumn(field="variable", title="Variable"), TableColumn(field="info", title="Info")]
    farm_info_table = DataTable(columns=farm_info_columns, source=farm_info_source, width = 200, height = 200)

    ##################### Emission Information Table
    emission_info_dict = {'ghg':['CH4', 'Direct N2O', 'Indirect N2O'],'value':[mean(ch4manure), mean(n2od_mm), mean(n2oid_mm)]}
    emission_info_source = ColumnDataSource(data=emission_info_dict)
    emission_info_columns = [TableColumn(field="ghg", title="GHG"), TableColumn(field="value", title="Value")]
    emission_info_table = DataTable(columns=emission_info_columns, source=emission_info_source, width = 400, height = 400)

    ######################## Intensity Meter
    # plot = figure(width = 10, height = 10,  y_range = (0, 0.04), x_range = (-0.5, 0.5)) 
    # plot.annular_wedge(x = 0, y = 0, inner_radius =.1,  
    #                outer_radius = 0.2, start_angle = 0, 
    #                end_angle = 3.14, fill_color ="green") 
    # #plot.axis.visible = False
    # plot.background_fill_color = "white"
    # https://github.com/bokeh/bokeh/blob/branch-2.3/examples/models/file/gauges.py

    ###################### Bar Chart 
    p_bar = figure(x_range= emission_info_source.data['ghg'], y_axis_label = 'Emission', title="GHG from Manure",plot_width=250, plot_height=250, 
                        background_fill_color="white")
    p_bar.vbar(x='ghg', top='value', width=0.25, source=emission_info_source)
    p_bar.sizing_mode = 'scale_width'

    ###################### Time series
    ghg_manure = ghg_manure.to_frame().reset_index()
    ghg_manure = ghg_manure.rename(columns={'index': 'Year', 0: 'GHG'})
    ghg_manure_source = ColumnDataSource(data=ghg_manure) 

    p_series = figure(x_axis_label ='Year', y_axis_label = 'CO2', plot_width=250, plot_height=250, 
                        background_fill_color="white")
    p_series.line(x='Year', y= 'GHG', source= ghg_manure_source)
    p_series.sizing_mode = 'scale_width'
  

    ##################### Rendering Plot
    #layout = column(row(farm_info_table, emission_info_table), row(p_bar, p_series))
    layout = (gridplot([[farm_info_table, emission_info_table],[p_bar, p_series]]))
    doc.add_root(layout)
    doc.theme = Theme(filename="theme.yaml")

# can't use shortcuts here, since we are passing to low level BokehTornado
bkapp = Application(FunctionHandler(bkapp))

# This is so that if this app is run using something like "gunicorn -w 4" then
# each process will listen on its own port
sockets, port = bind_sockets("localhost", 0)

@app.route('/', methods=['GET'])
def bkapp_page():
    script = server_document('http://localhost:%d/bkapp' % port)
    return render_template("embed.html", script=script, template="Flask")

def bk_worker():
    asyncio.set_event_loop(asyncio.new_event_loop())

    bokeh_tornado = BokehTornado({'/bkapp': bkapp}, extra_websocket_origins=["127.0.0.1:8000", "localhost:8000"])
    bokeh_http = HTTPServer(bokeh_tornado)
    bokeh_http.add_sockets(sockets)

    server = BaseServer(IOLoop.current(), bokeh_tornado, bokeh_http)
    server.start()
    server.io_loop.start()

t = Thread(target=bk_worker)
# t.daemon = True
t.start()
