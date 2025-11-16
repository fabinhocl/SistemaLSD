import dash
from dash import html

app = dash.Dash(__name__)
app.layout = html.Div("Teste dash standalone!")
app.run_server(debug=True)
