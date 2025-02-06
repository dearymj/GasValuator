"""
Simple Tkinter GUI to Price a Natural Gas Storage Contract

Steps:
1. User enters injection & withdrawal info (date, volume).
2. User enters costs & storage details.
3. On "Calculate Value", it uses the existing 'price_contract' logic
   to compute the net contract value and displays it.

Dependencies:
    pip install prophet
    pip install pandas
    (Tkinter is included by default with most Python installations)
"""

import tkinter as tk
import logging
import pandas as pd
from prophet import Prophet
from datetime import datetime

# ---------------------------------------------------------------------
# Suppress cmdstanpy logs
logging.getLogger("cmdstanpy").setLevel(logging.ERROR)

# -------------------------- PROPHET HELPERS --------------------------

def load_data(csv_file: str) -> pd.DataFrame:
    df = pd.read_csv(csv_file)
    df['Dates'] = pd.to_datetime(df['Dates'], format='%m/%d/%y')
    df.rename(columns={'Dates': 'ds', 'Prices': 'y'}, inplace=True)
    df.sort_values('ds', inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df

def train_prophet_model(df: pd.DataFrame) -> Prophet:
    model = Prophet(yearly_seasonality=True, weekly_seasonality=False, daily_seasonality=False)
    model.fit(df)
    return model

def get_price_estimate(model: Prophet, input_date: str) -> float:
    df_input = pd.DataFrame({'ds': [pd.to_datetime(input_date)]})
    forecast_input = model.predict(df_input)
    return float(forecast_input['yhat'].iloc[0])

# --------------------- CONTRACT PRICING LOGIC -----------------------

def price_contract(
    injection_events: list,
    withdrawal_events: list,
    model: Prophet = None,
    storage_monthly_fee: float = 0.0,
    injection_fee: float = 0.0,
    withdrawal_fee: float = 0.0,
    max_storage: float = 1e6,
) -> float:
    # Sort events
    all_events = []
    for ie in sorted(injection_events, key=lambda x: x['date']):
        all_events.append({'date': ie['date'], 'volume': ie['volume'], 'type': 'injection'})
    for we in sorted(withdrawal_events, key=lambda x: x['date']):
        all_events.append({'date': we['date'], 'volume': we['volume'], 'type': 'withdrawal'})
    all_events.sort(key=lambda x: x['date'])

    inventory = 0.0
    net_value = 0.0
    prev_date = None

    for event in all_events:
        current_date_str = event['date']
        volume = event['volume']
        etype = event['type']

        # 1. Storage costs from prev date to current date
        if prev_date is not None:
            months_diff = months_between(prev_date, current_date_str)
            storage_cost = inventory * storage_monthly_fee * months_diff
            net_value -= storage_cost

        # 2. Injection or withdrawal
        if etype == 'injection':
            if inventory + volume > max_storage:
                raise ValueError(f"Injection of {volume} exceeds max storage of {max_storage}!")
            price = get_price_estimate(model, current_date_str)
            net_value -= (price * volume)          # buy gas
            net_value -= (injection_fee * volume)  # injection fee
            inventory += volume

        elif etype == 'withdrawal':
            if inventory < volume:
                raise ValueError(f"Withdraw {volume} but only {inventory} in storage!")
            price = get_price_estimate(model, current_date_str)
            net_value += (price * volume)          # sell gas
            net_value -= (withdrawal_fee * volume) # withdrawal fee
            inventory -= volume

        prev_date = current_date_str

    return net_value

def months_between(date_str1: str, date_str2: str) -> float:
    d1 = datetime.strptime(date_str1, "%Y-%m-%d")
    d2 = datetime.strptime(date_str2, "%Y-%m-%d")
    diff_days = (d2 - d1).days
    avg_days_per_month = 365.25 / 12
    return diff_days / avg_days_per_month

# --------------------- TKINTER GUI ---------------------
class ContractPricingApp:
    def __init__(self, master, prophet_model: Prophet):
        self.master = master
        self.master.title("Natural Gas Contract Pricing | BY MJ Yuan")

        self.model = prophet_model

        # 1. Injection Input
        tk.Label(master, text="Injection Date (YYYY-MM-DD):").grid(row=0, column=0, sticky='e')
        self.inj_date_entry = tk.Entry(master)
        self.inj_date_entry.grid(row=0, column=1)
        self.inj_date_entry.insert(0, "2023-06-01")  # default example

        tk.Label(master, text="Injection Volume (MMBtu):").grid(row=1, column=0, sticky='e')
        self.inj_volume_entry = tk.Entry(master)
        self.inj_volume_entry.grid(row=1, column=1)
        self.inj_volume_entry.insert(0, "200000")  # default example

        # 2. Withdrawal Input
        tk.Label(master, text="Withdrawal Date (YYYY-MM-DD):").grid(row=2, column=0, sticky='e')
        self.wth_date_entry = tk.Entry(master)
        self.wth_date_entry.grid(row=2, column=1)
        self.wth_date_entry.insert(0, "2023-12-01")  # default example

        tk.Label(master, text="Withdrawal Volume (MMBtu):").grid(row=3, column=0, sticky='e')
        self.wth_volume_entry = tk.Entry(master)
        self.wth_volume_entry.grid(row=3, column=1)
        self.wth_volume_entry.insert(0, "200000")  # default example

        # 3. Fees & Storage
        tk.Label(master, text="Storage Monthly Fee ($/MMBtu/Month):").grid(row=4, column=0, sticky='e')
        self.storage_fee_entry = tk.Entry(master)
        self.storage_fee_entry.grid(row=4, column=1)
        self.storage_fee_entry.insert(0, "0.02")

        tk.Label(master, text="Injection Fee ($/MMBtu):").grid(row=5, column=0, sticky='e')
        self.injection_fee_entry = tk.Entry(master)
        self.injection_fee_entry.grid(row=5, column=1)
        self.injection_fee_entry.insert(0, "0.10")

        tk.Label(master, text="Withdrawal Fee ($/MMBtu):").grid(row=6, column=0, sticky='e')
        self.withdrawal_fee_entry = tk.Entry(master)
        self.withdrawal_fee_entry.grid(row=6, column=1)
        self.withdrawal_fee_entry.insert(0, "0.05")

        tk.Label(master, text="Max Storage (MMBtu):").grid(row=7, column=0, sticky='e')
        self.max_storage_entry = tk.Entry(master)
        self.max_storage_entry.grid(row=7, column=1)
        self.max_storage_entry.insert(0, "600000")

        # 4. Output
        self.result_label = tk.Label(master, text="Contract Value: ")
        self.result_label.grid(row=9, column=0, columnspan=2, sticky='w', pady=10)

        # 5. Button
        calc_btn = tk.Button(master, text="Calculate Value", command=self.calculate_value)
        calc_btn.grid(row=8, column=0, columnspan=2, pady=5)

    def calculate_value(self):
        # Gather inputs
        inj_date = self.inj_date_entry.get()
        inj_volume = float(self.inj_volume_entry.get())
        wth_date = self.wth_date_entry.get()
        wth_volume = float(self.wth_volume_entry.get())

        storage_fee = float(self.storage_fee_entry.get())
        inj_fee = float(self.injection_fee_entry.get())
        wth_fee = float(self.withdrawal_fee_entry.get())
        max_sto = float(self.max_storage_entry.get())

        # Construct injection/withdrawal lists
        injection_events = [{'date': inj_date, 'volume': inj_volume}]
        withdrawal_events = [{'date': wth_date, 'volume': wth_volume}]

        # Price the contract
        try:
            val = price_contract(
                injection_events=injection_events,
                withdrawal_events=withdrawal_events,
                model=self.model,
                storage_monthly_fee=storage_fee,
                injection_fee=inj_fee,
                withdrawal_fee=wth_fee,
                max_storage=max_sto
            )
            self.result_label.config(text=f"Contract Value: ${val:,.2f}")
        except ValueError as ve:
            self.result_label.config(text=f"Error: {ve}")

# --------------------- MAIN ---------------------
if __name__ == "__main__":

    # 1. Load data & train Prophet model
    csv_file_path = "Nat_Gas.csv"  # adapt path if needed
    df_prices = load_data(csv_file_path)
    prophet_model = train_prophet_model(df_prices)

    # 2. Launch Tkinter window
    root = tk.Tk()
    app = ContractPricingApp(root, prophet_model)
    root.mainloop()
