# -*- coding: utf-8 -*-
"""
Created on Mon Sep 25 12:36:39 2017

@author: Jim Lung
"""
import pandas as ps
from pandas.io.json import json_normalize
from flask import Flask, render_template, request
import pymongo
import requests
from bs4 import BeautifulSoup
from decimal import Decimal
from re import sub
import datetime
import json
from model import model_form
from bson import json_util
import matplotlib.pyplot as plot

app = Flask(__name__)

client = pymongo.MongoClient('mongodb://localhost:27017/')

db = client['trader']

blotters = db.blotter


def companieslist():
        url = 'http://www.nasdaq.com/screening/companies-by-industry.aspx?exchange=NASDAQ&render=download'
        df1 = ps.read_csv(url)
        df1 = df1.loc[:, ~df1.columns.str.contains('^Unnamed')]
        return df1


def analysis(symbol):
        url = 'http://www.nasdaq.com/symbol/' + symbol + '/historical'
        r = requests.get(url)
        data = r.text
        soup = BeautifulSoup(data, "lxml")
        table = soup.find('div', id="historicalContainer")
        header = ['Date', 'Open', 'High', 'Low', 'Close/Last', 'Volume']
        body = [[td.text.strip() for td in row.select('td') if td.text.strip() != ' ']
                for row in table.findAll('tr')]
        body = [x for x in body if x != []]
        df = ps.DataFrame(body, columns=header)
        df = df[1:len(df)]
        col = df.columns.values.tolist()
        for i in range(1, len(col) - 1):
                df[col[i]] = df[col[i]].apply(ps.to_numeric)
        summary = df.describe()
        return (summary)


def graphic(symbol):
        url2 = 'http://www.nasdaq.com/symbol/' + symbol + '/time-sales'
        r2 = requests.get(url2)
        data2 = r2.text
        soup2 = BeautifulSoup(data2, "lxml")
        table2 = soup2.find('div', id="quotes_content_left__panelTradeData")
        header2 = ['NLS Time (ET)', 'NLS Price', 'NLS Share Volume']
        body2 = [[td.text.strip() for td in row.select('td') if td.text.strip() != ' ']
                 for row in table2.findAll('tr')]
        body2 = [x for x in body2 if x != []]
        dft = ps.DataFrame(body2, columns=header2)

        url3 = 'http://www.nasdaq.com/symbol/' + symbol + '/time-sales?pageno=2'
        r3 = requests.get(url3)
        data3 = r3.text
        soup3 = BeautifulSoup(data3, "lxml")
        table3 = soup3.find('div', id="quotes_content_left__panelTradeData")
        header3 = ['NLS Time (ET)', 'NLS Price', 'NLS Share Volume']
        body3 = [[td.text.strip() for td in row.select('td') if td.text.strip() != ' ']
                 for row in table3.findAll('tr')]
        body3 = [x for x in body3 if x != []]
        cols3 = zip(*body3)
        tbl_d3 = {name: col for name, col in zip(header3, cols3)}
        dft2 = ps.DataFrame(tbl_d3, columns=header3)
        groupdft = dft.append(dft2, ignore_index=True)
        xaxis = ps.to_datetime(groupdft['NLS Time (ET)'])
        yaxis = groupdft['NLS Price']
        graph = plot.plot(xaxis, yaxis)
        return (graph)


def pricesnow(symbol):
        url = 'http://www.nasdaq.com/symbol/' + symbol
        r = requests.get(url)
        data = r.text
        soup = BeautifulSoup(data, "lxml")
        price = soup.find('div', {'class': 'qwidget-dollar'}).text
        currentprice = float(Decimal(sub(r'[^\d.]', '', price)))
        return currentprice


def buy(table, symbol, shares):
        url = 'http://www.nasdaq.com/symbol/' + symbol
        time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        r = requests.get(url)
        data = r.text
        soup = BeautifulSoup(data, "lxml")
        price = soup.find('div', {'class': 'qwidget-dollar'}).text
        currentprice = float(Decimal(sub(r'[^\d.]', '', price)))

        sharesymbol = symbol

        sharecost = currentprice * shares
        if table.empty == True:
                balance = 10000000 - sharecost
        else:
                balance = cashremain(table) - sharecost

        if table.empty == True:
                WAP = currentprice
        else:
                y = pl(table)
                if y[y.Ticker == sharesymbol].empty == True:
                        WAP = currentprice
                else:
                        y = y[y.Ticker == sharesymbol]
                        WAP = float(ps.to_numeric(y.iloc[:, 4]))

        newrecord = ['buy', sharesymbol, shares, currentprice, time, sharecost * -1, WAP, balance]
        return newrecord


def sell(table, symbol, shares):
        url = 'http://www.nasdaq.com/symbol/' + symbol
        time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        r = requests.get(url)
        data = r.text
        soup = BeautifulSoup(data, "lxml")
        price = soup.find('div', {'class': 'qwidget-dollar'}).text
        currentprice = float(Decimal(sub(r'[^\d.]', '', price)))
        sharesymbol = symbol
        # WAP
        sharecost = currentprice * shares
        if table.empty == True:
                balance = 10000000 + sharecost
        else:
                balance = cashremain(table) + sharecost

        if table.empty == True:
                WAP = currentprice
        else:
                y = pl(table)
                if y[y.Ticker == sharesymbol].empty == True:
                        WAP = currentprice
                else:
                        y = y[y.Ticker == sharesymbol]
                        WAP = float(ps.to_numeric(y.iloc[:, 3]))

        newrecord = ['sell', sharesymbol, shares, currentprice, time, sharecost, WAP, balance]
        return newrecord


def cashremain(table):
        cash = 10000000
        x = table
        newcash = float(cash + sum(x.Cost))
        return newcash


def stockremain(table, sharesymbol):
        x = table
        if x.empty == True:
                stocks = 0
        else:
                l = x[(x.Ticker == sharesymbol)]
                stocks = sum(l.Qty)
        return stocks


def insert(newrecord):
        Side = newrecord[0]
        Ticker = newrecord[1]
        Qty = newrecord[2]
        Price = float(newrecord[3])
        Date = newrecord[4]
        Cost = float(newrecord[5])
        TWAP = float(newrecord[6])
        balance = newrecord[7]

        k = db.blotter.count()

        myrecord = {
                "_id": k,
                "balance": balance,
                "Cost": Cost,
                "Date": Date,
                "Price": Price,
                "Qty": Qty,
                "Side": Side,
                "Ticker": Ticker,
                "TWAP": TWAP
        }
        record_id = db.blotter.insert_one(myrecord)
        return record_id


def pl(table):
        x = table
        col = x.Ticker.unique().tolist()
        y = ps.DataFrame(ps.np.empty((len(col), 9)),
                         columns=['Ticker', 'Position', 'Market', 'WAP', 'UPL', 'RPL', 'Total', 'AllocationShares',
                                  'AllocationDollars'])
        y.Ticker = col
        for i in range(0, len(col)):
                symbol = col[i]
                instantprice = pricesnow(symbol)
                y['Market'][y.Ticker == symbol] = instantprice

        # WAP
        l = []
        r = []
        for i in range(0, len(col)):
                l = x[(x.Side == 'buy') & (x.Ticker == col[i])]
                r = x[(x.Ticker == col[i])]
                r.loc[r.Side == 'sell', 'Qty'] *= -1
                if sum(l.Qty) == 0:
                        y.WAP[i] = 0
                        y.Position[i] = sum(r.Qty)
                else:
                        l.Cost = l.Qty * l.Price
                        y.WAP[i] = sum(l.Cost) / sum(l.Qty)
                        y.Position[i] = sum(r.Qty)

        # UPL
        for i in range(0, len(col)):
                if y.Position[i] > 0:
                        if float((y.Market[i] - y.WAP[i]) * y.Position[i]) < 0.01:
                                y.UPL[i] = 0
                        else:
                                y.UPL[i] = float((y.Market[i] - y.WAP[i]) * y.Position[i])
                else:
                        y.UPL[i] = 0

        # RPL
        for i in range(0, len(col)):
                r = x[(x.Side == 'sell') & (x.Ticker == col[i])]
                if r.empty == False:
                        r['Profit'] = r.Qty * (r.Price - r.TWAP)
                        if sum(r.Qty) == 0:
                                y.RPL[i] = format(0, '.2f')
                        else:
                                y.RPL[i] = format(sum(r.Profit), '.2f')
                else:
                        y.RPL[i] = 0

        # calcualte total UPL + RPL
        y['Total'] = y['UPL'] + y['RPL']
        y['AllocationShares'] = y['Position'] / y['Position'].sum()
        y['AllocationDollars'] = y['Market'] / y['Market'].sum()
        y = y.fillna(0)

        return y


@app.route('/')
@app.route('/index')
def index():
        return render_template('mainpage.html')


@app.route('/buy', methods=['GET', 'POST'])
def buyhtml():
        dbsort = db.blotter.find().sort('Date', -1)
        e = ps.DataFrame(json_normalize(json.loads(json_util.dumps(dbsort))))
        df2 = companieslist()
        df1 = df2.reset_index()[['index', 'Symbol']].values.tolist()
        form = model_form(request.form)
        form.Symbol.choices = df1
        my = companieslist()
        if e.empty == True:
                z = 10000000
        else:
                z = cashremain(e)
        if request.method == 'POST' and form.validate() and request.form['chart'] == 'Price':
                indexed = my[my.Symbol == form.Symbol.data].empty
                if indexed == False:
                        result = graphic(form.Symbol.data)
                        currentprice = pricesnow(form.Symbol.data)
                        newrecord = None
                        record = None
                        analytic = analysis('AAPL')
                        message = 'Trading details'
                else:
                        result = None
                        currentprice = None
                        newrecord = None
                        record = None
                        analytic = analysis('AAPL')
                        message = None
        elif request.method == 'POST' and form.validate() and request.form['chart'] == 'Buy':
                indexed = my[my.Symbol == form.Symbol.data].empty
                if indexed == False:
                        newrecord = buy(e, form.Symbol.data, form.Qty.data)
                        if z >= newrecord[5] * -1:
                                result = graphic(form.Symbol.data)
                                currentprice = pricesnow(form.Symbol.data)
                                newrecord = newrecord
                                record = insert(newrecord)
                                analytic = analysis(form.Symbol.data)
                                message = 'Make transaction!'
                        else:
                                result = None
                                currentprice = None
                                newrecord = None
                                record = None
                                analytic = analysis(form.Symbol.data)
                                message = "Not a transaction"
                else:
                        result = None
                        currentprice = None
                        newrecord = None
                        record = None
                        analytic = analysis('AAPL')
                        message = "Not a transaction"
        else:
                result = None
                currentprice = None
                newrecord = None
                record = None
                analytic = analysis(form.Symbol.data)
                message = 'Trading option!'
        return render_template('buy.html', form=form, data=df1, analytic=analytic.to_html(), result=result,
                               record=record, currentprice=currentprice, message=message, newrecord=newrecord)


@app.route('/sell', methods=['GET', 'POST'])
def sellhtml():
        dbsort = db.blotter.find().sort('Date', -1)
        e = ps.DataFrame(json_normalize(json.loads(json_util.dumps(dbsort))))
        df2 = companieslist()
        df1 = df2.reset_index()[['index', 'Symbol']].values.tolist()
        form = model_form(request.form)
        form.Symbol.choices = df1
        if e.empty == True:
                z = 0
        else:
                z = stockremain(e, form.Symbol.data)
        if request.method == 'POST' and form.validate() and request.form['chart'] == 'Price and Analysis':

                result = graphic(form.Symbol.data)
                currentprice = pricesnow(form.Symbol.data)
                newrecord = None
                record = None
        elif e.empty == True and request.method == 'POST' and form.validate() and request.form['chart'] == 'Sell':
                result = None
                currentprice = None
                newrecord = None
                record = None
        elif request.method == 'POST' and form.validate() and request.form['chart'] == 'Sell':
                newrecord = sell(e, form.Symbol.data, form.Qty.data)
                if z >= newrecord[2]:
                        result = graphic(form.Symbol.data)
                        currentprice = pricesnow(form.Symbol.data)
                        record = insert(newrecord)
                else:
                        result = None
                        currentprice = None
                        newrecord = None
                        record = None
        else:
                result = None
                currentprice = None
                newrecord = None
                record = None
        return render_template('sell.html', form=form, data=df1, result=result, record=record,
                               currentprice=currentprice, newrecord=newrecord)


@app.route('/blotter', methods=['GET', 'POST'])
def blotter():
        dbsort = db.blotter.find().sort('Date', -1)
        e = ps.DataFrame(json_normalize(json.loads(json_util.dumps(dbsort))))
        if e.empty == True:
                message = "No Trading record"
                blotterstable = None
        else:
                message = "Blotter record"
                blotterstable = blotters.find()
        return render_template('blotter.html', blotters=blotterstable, message=message)


@app.route('/pls', methods=['GET', 'POST'])
def pls():
        dbsort = db.blotter.find()
        e = ps.DataFrame(json_normalize(json.loads(json_util.dumps(dbsort))))
        if e.empty == True:
                message = "No trading record"
                l = None
        else:
                z = pl(e)
                message = "P/L record"
                l = z.to_html()
        return render_template('pl.html', blotters=l, message=message)


if __name__ == '__main__':
        app.run(host='0.0.0.0', debug=True)
