# -*- coding: utf-8 -*-
"""
Created on Sun Feb 13 20:47:30 2022

@author: scedermas
"""

# Originally published under
# http://wanlinksniper.blogspot.com.es/2014/05/erlang-c-en-python-herramientas-para-el.html
# A few Python routines I put together one evening to compute
# traffic intensity, agent occupancy, probability of waiting,
# average speed of answer (ASA), service level, agents needed and other Erlang-C related stuff.
# broken link: http://www.mitan.co.uk/erlang/elgcmath.htm
# wayback machine: https://web.archive.org/web/20181209042241/http://www.mitan.co.uk/erlang/elgcmath.htm
# Python3 ported April 2021

from math import pow,factorial,log,exp

import pandas as pd
import sqlite3
import streamlit as st
import matplotlib.pyplot as plt
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px
import datetime as dt

con = sqlite3.connect("priority.db")

def PowerFact(b,e):
    """
    Returns b^e / e! used everywhere else in the model
    
    Parameters:
        b (int): base
        e (int): exponent
    """
    return pow(b,e)/factorial(e)

def erlangC(m,u):
    """
    Returns the probability a call waits.

    Parameters:
        m   (int): agent count
        u (float): traffic intensity
    """
    p = u/m  ##  agent occupancy
    suma = 0
    for k in range(0,m):
        suma += PowerFact(u,k)
    erlang = PowerFact(u,m) / ((PowerFact(u,m)) + (1-p)*suma)
    return erlang

def SLA(m,u,T,target):
    """
    Returns the average speed of answer
    
    Parameters:
        m        (int): agent count
        u      (float): traffic intensity
        T      (float): average call time
        target (float): target answer time
    """
    return (1 - erlangC(m, u) * exp(-(m-u) * (target/T)))

def ASA(m,u,T):
    """
    Returns the average speed of answer (ASA)
    
    Parameters:
        m   (int): agent count
        u (float): traffic intensity
        T (float): average call time
    """
    return erlangC(m, u) * (T/(m-u))

def agentsNeeded(u,T,targetSLA,target):
    """
    Returns the number of agents needed to reach given SLA
    
    Parameters:
        u         (float): traffic intensity
        T         (float): average call time
        target    (float): target answer time
        targetSLA (float): % representing calls answered under target time
    """
    level=0
    m=1
    while level<targetSLA:
        level = SLA(m,u,T,target)
        m += 1
    return m-1
    

def showStats(calls,interval,T,m,target,level):
    """
    Prints Erlang related statistics

    Parameters:
        calls    (int): calls received in a given time interval
        interval (int): time interval in secs (i.e. 1800s == 30m)
        T        (int): average call time, in secs
        m        (int): number of agents
    
    Intermediate results:    
        landa       calls/interval
        u=landa*T   traffic intensity
        p=u/m       agent occupancy
    """
    landa = calls/interval
    u=landa*T      # traffic intensity
    p=u/m          # agent occupancy
    # print('calls: {}   interval: {}   landa: {:.8f} (l = calls/interval)'.format(calls, interval, landa))
    # print('traffic intensity: {:.2f}   agents: {}    agent occupancy: {:.2f}'.format(u,m,p))
    # print('ErlangC, Probability of waiting: {:.2f}%'.format(erlangC(m,u)*100))
    # print('ASA, Average speed of answer: {:.1f} secs'.format(ASA(m,u,T)))
    # print('Probability call is answered in less than {} secs: {:.2f}%'.format(target,SLA(m,u,T,target)*100))
    print('Agents needed to reach {:.2f}% calls answered in <{} secs: {}'.format(level*100,target,agentsNeeded(u,T,level,target)))

def main():
    """
    Runs Erlang tests

    Parameters:
        calls    (int): calls received in a given time interval
        interval (int): time interval in secs (i.e. 1800s == 30m)
        T        (int): average call time, in secs
        m        (int): number of agents
    
    Intermediate results:    
        landa       calls/interval
        u=landa*T   traffic intensity
        p=u/m       agent occupancy
    """

    TESTS = [
        #calls,interval,T,m,target,level
        [360, 1800,  240, 55,   15, 0.70],
        [300,  900,  180, 65,   45, 0.95],
        [100, 3600,  456, 34,   60, 0.60],
        [20,  3600, 1800, 11, 3600, 0.80]
    ]

    for dataset in TESTS:
        calls,interval,T,m,target,level = dataset
        showStats(calls,interval,T,m,target,level)
        print("-"*10)

# if __name__ == "__main__":
#     main()

informe = st.sidebar.selectbox('Elegí una de las opciones', ("Configuracion", 'Valores consolidades mes y diarios', 'Detalle un dia', 'Detalle Intervalos'))
if informe=="Configuracion":
    configuracion=pd.read_sql('SELECT * from configuracion', con)
    tmo=st.sidebar.number_input("TMO: ", value=configuracion.loc[0, "tmo"])
    ns=st.sidebar.number_input("Nivel de Servicio: ", value=configuracion.loc[0, "ns"])
    umbral=st.sidebar.number_input("Umbral (s): ", value=configuracion.loc[0, "umbral"])
    tasa_aband=st.sidebar.number_input("Tasa de abandono: ",value=configuracion.loc[0, "tasa_aband"])
    calcular=st.sidebar.button("Calcular")
    
    
    if calcular:
        cursorobj=con.cursor() 
        cursorobj.execute('update configuracion set tmo="'+str(tmo)+'", ns="'+str(ns)+'", umbral="'+str(umbral)+'", tasa_aband="'+str(tasa_aband)+'";')
        con.commit() 

        datos=pd.read_sql('SELECT * from pronostico', con)
        datos.Volumen_pronostico=datos.Volumen_pronostico.astype(float)
        
        for i in range(len(datos)):
            datos.loc[i,"rac_nec"]= agentsNeeded( datos.loc[i,"Volumen_pronostico"]/1800*tmo, tmo, ns, umbral)
        datos["workload"]=datos["Volumen_pronostico"]*tmo*(1-tasa_aband)/1800
        datos["ocupacion"]=datos["workload"]/datos["rac_nec"]
        datos.to_sql("resultados", con, if_exists="replace")  
    
        resultados=pd.read_sql('SELECT * from resultados', con)
        total_llamadas=resultados["Volumen_pronostico"].sum()
        st.success("Datos actualizados y se calcularon nuevamente los parametros")
    else:
        st.header("Analisis dimensionamiento y avail diseño")
        st.subheader("Priority Argentina Enero2022")
        st.text("por favor elija una opcion del menú")
        # st.text(total_llamadas)
    # print (total_llamadas)
    # workload=resultados["workload"].sum()/2
    # total_horas_rac_erlang=resultados["rac_nec"].sum()/2
    # print(workload)
    # print(total_horas_rac_erlang)
    # st.text(workload/total_horas_rac_erlang)
    
    
    # # print(workload/total_horas_rac_erlang)
    
    
    
    # grupo_fecha=resultados.groupby(by="Fecha").sum()
    # grupo_fecha["rac_nec"]=grupo_fecha["rac_nec"]/2
    # st.table(grupo_fecha)
if informe=="Valores consolidades mes y diarios":
    configuracion=pd.read_sql('SELECT * from configuracion', con)
    st.sidebar.text("Datos de configuración")
    st.sidebar.text("TMO: "+str(configuracion.loc[0,"tmo"]))
    st.sidebar.text("Nivel Servicio: "+str(configuracion.loc[0,"ns"]))
    st.sidebar.text("Umbral: "+str(configuracion.loc[0,"umbral"]))
    st.sidebar.text("Tasa Aband: "+str(configuracion.loc[0,"tasa_aband"])) 
    dato_mes=pd.read_sql('SELECT mes, sum(Volumen_pronostico) as volumen_prono, sum(rac_nec)/2 as horas_racs_prod, sum(workload)/2 as workload, 100*sum(workload)/sum(rac_nec) as ocupacion from resultados group by mes', con)
    st.table(dato_mes.style.format('{:7,.1f}'))
    
    racs_nominales=int(dato_mes.loc[0,"horas_racs_prod"]/120/.76)
    st.text("Racs nominales 120hs mes: "+str(racs_nominales))
    dato_dia=pd.read_sql('SELECT Fecha, sum(Volumen_pronostico) as volumen_prono, sum(rac_nec)/2 as horas_racs_prod, sum(workload)/2 as workload, 100*sum(workload)/sum(rac_nec) as ocupacion from resultados group by Fecha', con)

    
    # fig1 = go.Figure()
    fig1 = make_subplots(specs=[[{"secondary_y": True}]])
 
    fig1.add_trace(go.Scatter(x=dato_dia["Fecha"], y=dato_dia["ocupacion"],name="Ocupacion"),secondary_y=True)

    fig1.add_trace(go.Scatter(x=dato_dia["Fecha"], y=dato_dia["volumen_prono"],name="Volumen Pronosticado"))

    fig1.update_xaxes(type='category')
    fig1.update_layout(height=450, width=1200)
    st.plotly_chart(fig1, use_container_width=True)
    
    st.subheader("Histograma Ocupacion")
    fig, ax = plt.subplots()
    ax.hist(dato_dia["ocupacion"], bins=90)
    st.pyplot(fig)
    
    st.subheader("Volumen vs Ocupacion")
    fig2, ax2 = plt.subplots()
    ax2.scatter(dato_dia["ocupacion"],dato_dia["volumen_prono"])
    st.pyplot(fig2)
    
    st.table(dato_dia)
    
if informe=="Detalle un dia":    
    configuracion=pd.read_sql('SELECT * from configuracion', con)
    st.sidebar.text("TMO: "+str(configuracion.loc[0,"tmo"]))
    st.sidebar.text("Nivel Servicio: "+str(configuracion.loc[0,"ns"]))
    st.sidebar.text("Umbral: "+str(configuracion.loc[0,"umbral"]))
    st.sidebar.text("Tasa Aband: "+str(configuracion.loc[0,"tasa_aband"])) 
    ahora=dt.datetime.now()
    fecha_informe=st.sidebar.date_input('Fecha', dt.date(ahora.year, ahora.month, ahora.day))
    dato_intervalos=pd.read_sql('SELECT Intervalo, Volumen_pronostico, rac_nec, workload, workload/rac_nec as ocupacion from resultados where fecha = "'+str(fecha_informe)+'"', con)
    fig1 = make_subplots(specs=[[{"secondary_y": True}]])
 
    fig1.add_trace(go.Scatter(x=dato_intervalos["Intervalo"], y=dato_intervalos["ocupacion"],name="Ocupacion"),secondary_y=True)
    fig1.add_trace(go.Scatter(x=dato_intervalos["Intervalo"], y=dato_intervalos["rac_nec"],name="Racs Necesarios"))
    fig1.add_trace(go.Scatter(x=dato_intervalos["Intervalo"], y=dato_intervalos["workload"],name="workload"))
    fig1.add_trace(go.Scatter (x=dato_intervalos["Intervalo"], y=dato_intervalos["Volumen_pronostico"],name="Volumen Pronosticado"))

    fig1.update_xaxes(type='category')
    fig1.update_layout(height=450, width=1200)
    st.plotly_chart(fig1, use_container_width=True)
    st.table(dato_intervalos)

if informe=="Detalle Intervalos":
    configuracion=pd.read_sql('SELECT * from configuracion', con)
    st.sidebar.text("TMO: "+str(configuracion.loc[0,"tmo"]))
    st.sidebar.text("Nivel Servicio: "+str(configuracion.loc[0,"ns"]))
    st.sidebar.text("Umbral: "+str(configuracion.loc[0,"umbral"]))
    st.sidebar.text("Tasa Aband: "+str(configuracion.loc[0,"tasa_aband"])) 
    dato_intervalos=pd.read_sql('SELECT Fecha||" "|| Intervalo as fecha_hora, Fecha, Intervalo, Volumen_pronostico, rac_nec, workload, workload/rac_nec as ocupacion from resultados ', con)
  
    
    # fig1 = go.Figure()
    fig1 = make_subplots(specs=[[{"secondary_y": True}]])
 
    fig1.add_trace(go.Scatter(x=dato_intervalos["fecha_hora"], y=dato_intervalos["ocupacion"],name="Ocupacion"),secondary_y=True)

    fig1.add_trace(go.Scatter(x=dato_intervalos["fecha_hora"], y=dato_intervalos["Volumen_pronostico"],name="Volumen Pronosticado"))

    fig1.update_xaxes(type='category')
    fig1.update_layout(height=450, width=1200)
    st.plotly_chart(fig1, use_container_width=True)
    
    st.subheader("Histograma Ocupacion")
    fig, ax = plt.subplots()
    ax.hist(dato_intervalos["ocupacion"], bins=90)
    st.pyplot(fig)
    
    st.subheader("Volumen vs Ocupacion")
    fig2, ax2 = plt.subplots()
    ax2.scatter(dato_intervalos["ocupacion"],dato_intervalos["Volumen_pronostico"])
    st.pyplot(fig2)