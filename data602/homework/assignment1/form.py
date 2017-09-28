from flask import Flask, render_template, request


app = Flask(__name__)

@app.route('/')
def trade():
   return render_template('main.html')

@app.route('/trade',methods = ['POST', 'GET'])
def trade():
   if request.method == 'POST':
      trade = request.form
      return render_template("trade.html",trade = trade)

@app.route('/blotter',methods = ['POST', 'GET'])
def blotter():
   from bs4 import BeautifulSoup
   import requests
   import pandas as pd
   url = ['AAPL', 'AMZN', 'MSFT', 'INTC', 'SNAP']
   df = pd.DataFrame(columns=['Side', 'Quality', 'Executed Price', 'date'], index=[url])
   df[['Quality']] = df[['Quality']].apply(pd.to_numeric)

   def f(url2, i):
      page = requests.get(url2)
      soup = BeautifulSoup(page.content, 'html.parser')
      current = soup.find('span', class_='Trsdu(0.3s) Fw(b) Fz(36px) Mb(-4px) D(ib)').get_text()

      print(current)

      date = soup.find('div', class_='C($c-fuji-grey-j) D(b) Fz(12px) Fw(n) C($c-fuji-grey-j)').get_text()
      print(date)

      df.loc[i] = pd.Series({'Side': '', 'Quality': '', 'Executed Price': current, 'date': date})

   for i in url:
      url1 = "https://finance.yahoo.com/quote/{}?p=".format(i)
      url2 = url1 + i
      f(url2, i)

   blotter = pd.pivot_table(df, index=["Name"])
   return render_template('blotter.html', blotter=blotter)

@app.route('/PL',methods = ['POST', 'GET'])
def PL():
   import numpy as np
   b = np.zeros((6, 5))
   a = np.around(b, decimals=0)

   # Market price

   a[0, 1] = df.loc['AAPL', 'current']
   a[1, 1] = df.loc['AMZN', 'current']
   a[2, 1] = df.loc['MSFT', 'current']
   a[3, 1] = df.loc['INTC', 'current']
   a[4, 1] = df.loc['SNAP', 'current']

   # Buying price
   a[0, 2] = 150

   # Position
   a[0, 0] = 1000
   a[1, 0] = 12
   a[2, 0] = 2
   a[4, 0] = 3

   invest = 10000000
   a[5, 0] = invest - (a[0, 0] * a[0, 2])
   a[5, 1] = a[5, 0]

   for i in range(0, 4):
      if a[i, 1] - a[i, 2] > 0:
         a[i, 3] = (a[i, 1] - a[i, 2]) * a[i, 0]
      else:
         a[i, 4] = (a[i, 2] - a[i, 1]) * a[i, 0]

   PL = pd.DataFrame(a, columns=['position', 'Market', 'WAP', 'UPL', 'RPL'],
                    index=['AAPL', 'AMZN', 'MSFT', 'INTC', 'SNAP', 'CASH'])
   return render_template('PL.html', PL=PL)

if __name__ == '__main__':
   app.run(debug = True)