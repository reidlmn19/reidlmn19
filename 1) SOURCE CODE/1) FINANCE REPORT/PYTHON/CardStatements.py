from datetime import *
from tabulate import tabulate
import pandas as pd
import numpy as np
import PyPDF2
from StringTools import str_to_date, str_to_number


# For every card statement you need a summary including start date, end date,
# starting balance, and ending balance (for each account on the statement)
# The transaction table requires a Date, Amount, and Description. A Ledger is preferred but
# not necessary

def santander_transaction(s, account=None, years=None):
    df = pd.DataFrame()
    if 'Account Activity (Cont. for Acct#' in s:
        s = s.split('Page')[0]
    lst = s.split()
    if len(lst) > 3:
        try:
            df.at[0, 'Date'] = str_to_date(lst[0])[0]
            df.at[0, 'Description'] = ' '.join(lst[1:-2])
            df.at[0, 'Amount'] = str_to_number(lst[-2])
            df.at[0, 'Balance'] = str_to_number(lst[-1])

            if account is not None:
                df.at[0, 'Account'] = account

            if years is not None:
                if df.at[0, 'Date'].month == 1:
                    df.at[0, 'Date'] = df.at[0, 'Date'].replace(year=years[1])
                else:
                    df.at[0, 'Date'] = df.at[0, 'Date'].replace(year=years[0])
        except:
            return None
        if df.isnull().values.any():
            return None
        else:
            return df


class CardStatement:
    def __init__(self, path=None, account=None, institution=None, process=True):
        self.path = path
        self.account = account
        self.institution = institution

        self.rawdata = None
        self.summary = {}
        self.transactions = pd.DataFrame()
        if process:
            self.process()

    def process(self):
        self.get_rawdata()
        self.get_summary()
        self.get_transactions()

    def get_rawdata(self):
        pages_text = ''
        reader = PyPDF2.PdfReader(self.path)
        for page in reader.pages:
            page_text = page.extract_text()
            pages_text = pages_text + page_text
        self.rawdata = pages_text

    def get_summary(self):
        self.summary = {'Starting Balance': None,
                        'Ending Balance': None,
                        'Starting Date': None,
                        'Ending Date': None}

    def get_transactions(self):
        print(f'Get transactions not defined for {self.institution}')


class SantanderStatement(CardStatement):
    def __init__(self, path=None, account='Checking/Savings', institution='Santander', process=True):
        super().__init__(path=path, account=account, institution=institution, process=process)

    def get_summary(self, debug=False):
        lst = self.rawdata.split('\n')
        state = 0
        last_state = 0
        last_item = ''
        date_range = None

        if debug:
            print(lst)

        keywords = {
            'STUDENT VALUE CHECKING Statement Period': 1,
            'Balances': 2,
            'SANTANDER SAVINGS Statement Period': 3
        }

        for item in lst:
            item = item.strip()

            if state == 0:
                pass
            elif state == 1:
                splt = last_item.replace('STUDENT VALUE CHECKING Statement Period ', '').split()
                d1 = str_to_date(splt[0])
                d2 = str_to_date(splt[-1])
                if d1 is not None:
                    self.summary['Starting Date'] = d1[0]
                if d2 is not None:
                    self.summary['Ending Date'] = d2[0]
            elif state == 2:
                if last_state == 1:
                    if 'Beginning Balance ' in item:
                        a1 = str_to_number(item.replace('Beginning Balance ', '').split()[0])
                        if a1 is not None:
                            self.summary['Starting Balance Checking'] = a1
                    if 'Current Balance' in item:
                        a2 = str_to_number(item.split()[-1])
                        if a2 is not None:
                            self.summary['Ending Balance Checking'] = a2
                elif last_state == 3:
                    if 'Beginning Balance ' in item:
                        a1 = str_to_number(item.replace('Beginning Balance ', '').split()[0])
                        if a1 is not None:
                            self.summary['Starting Balance Savings'] = a1
                    if 'Current Balance' in item:
                        a2 = str_to_number(item.split()[-1])
                        if a2 is not None:
                            self.summary['Ending Balance Savings'] = a2
                last_state = state
                state = 0

            for key in keywords.keys():
                if key in item:
                    last_state = state
                    state = keywords[key]
                    last_item = item

    def get_transactions(self, debug=False):
        yr_rng = [self.summary['Starting Date'].year, self.summary['Ending Date'].year]
        state = 0
        last_state = 0
        account = 'Checking'
        text_buffer = ''
        lst = self.rawdata.split('\n')

        if debug:
            print(lst)

        keywords = {
            'Date Description Additions Subtractions Balance': 1,
            'Ending Balance': 3,
        }

        for item in lst:
            item = item.strip()

            if state == 0:
                pass
            elif state == 1:
                if 'Beginning Balance' in item:
                    if last_state == 0:
                        state = 2
                    elif last_state == 3:
                        state = 4
                elif last_state == 2:
                    state = 2
                elif last_state == 4:
                    state = 4
            elif state == 2:
                entry = santander_transaction(item, account=account, years=yr_rng)
                if entry is not None:
                    self.transactions = pd.concat([self.transactions, entry], ignore_index=True)
                    text_buffer = ''
                elif len(text_buffer) > 0:
                    entry = santander_transaction(f'{text_buffer} {item}'.replace('$', ' '),
                                                  account=account, years=yr_rng)
                    if entry is not None:
                        self.transactions = pd.concat([self.transactions, entry], ignore_index=True)
                        text_buffer = ''
                else:
                    text_buffer = text_buffer + item
            elif state == 3:
                if last_state == 4:
                    break
                else:
                    account = 'Savings'
                    text_buffer = ''
            elif state == 4:
                entry = santander_transaction(item, account=account, years=yr_rng)
                if entry is not None:
                    self.transactions = pd.concat([self.transactions, entry], ignore_index=True)
                    text_buffer = ''
                elif len(text_buffer) > 0:
                    entry = santander_transaction(f'{text_buffer} {item}'.replace('$', ' '),
                                                  account=account, years=yr_rng)
                    if entry is not None:
                        self.transactions = pd.concat([self.transactions, entry], ignore_index=True)
                        text_buffer = ''
                else:
                    text_buffer = text_buffer + item

            if item in keywords.keys():
                last_state = state
                state = keywords[item]
            else:
                for key in keywords.keys():
                    if key in item:
                        last_state = state
                        state = keywords[key]
        self.fix_amount_signs()
        self.transactions['Institution'] = self.institution

    def fix_amount_signs(self):
        check_balance = pd.DataFrame({'Date': self.summary['Starting Date'],
                                      'Description': 'Ignore',
                                      'Amount': 0,
                                      'Balance': self.summary['Starting Balance Checking'],
                                      'Account': 'Checking'}, index=[0])
        save_balance = pd.DataFrame({'Date': self.summary['Starting Date'],
                                     'Description': 'Ignore',
                                     'Amount': 0,
                                     'Balance': self.summary['Starting Balance Savings'],
                                     'Account': 'Savings'}, index=[0])
        self.transactions = pd.concat([check_balance, save_balance, self.transactions]).reset_index(drop=True)

        df1 = self.transactions.set_index('Date')
        df1 = df1[df1['Account'] == 'Checking']
        df1['Sign1'] = df1['Balance'].diff() < 0
        df1['Amount'] = np.where(df1['Sign1'], -df1['Amount'], df1['Amount'])

        df2 = self.transactions.set_index('Date')
        df2 = df2[df2['Account'] == 'Savings']
        df2['Sign2'] = df2['Balance'].diff() < 0
        df2['Amount'] = np.where(df2['Sign2'], -df2['Amount'], df2['Amount'])

        self.transactions = pd.concat([df1, df2]).drop(columns=['Sign1', 'Sign2'])
        self.transactions = self.transactions.drop(self.transactions[self.transactions['Amount'] == 0].index)
        self.transactions.reset_index(inplace=True)


class PeoplesStatement(CardStatement):
    def __init__(self, path=None, account='Checking', institution='Peoples', process=True):
        super().__init__(path=path, account=account, institution=institution, process=process)


class CapitalOneStatement(CardStatement):
    def __init__(self, path=None, account=None, institution='CapitalOne', process=True):
        super().__init__(path=path, account=account, institution=institution, process=process)

    def get_summary(self, debug=False):
        lst = self.rawdata.split('\n')
        state = 0
        last_state = 0
        last_item = ''
        date_range = None

        if debug:
            print(lst)

        keywords = {
            'STUDENT VALUE CHECKING Statement Period': 1,
            'Balances': 2,
            'SANTANDER SAVINGS Statement Period': 3
        }

        for item in lst:
            item = item.strip()

            if state == 0:
                pass
            elif state == 1:
                splt = last_item.replace('STUDENT VALUE CHECKING Statement Period ', '').split()
                d1 = str_to_date(splt[0])
                d2 = str_to_date(splt[-1])
                if d1 is not None:
                    self.summary['Starting Date'] = d1[0]
                if d2 is not None:
                    self.summary['Ending Date'] = d2[0]
            elif state == 2:
                if last_state == 1:
                    if 'Beginning Balance ' in item:
                        a1 = str_to_number(item.replace('Beginning Balance ', '').split()[0])
                        if a1 is not None:
                            self.summary['Starting Balance Checking'] = a1
                    if 'Current Balance' in item:
                        a2 = str_to_number(item.split()[-1])
                        if a2 is not None:
                            self.summary['Ending Balance Checking'] = a2
                elif last_state == 3:
                    if 'Beginning Balance ' in item:
                        a1 = str_to_number(item.replace('Beginning Balance ', '').split()[0])
                        if a1 is not None:
                            self.summary['Starting Balance Savings'] = a1
                    if 'Current Balance' in item:
                        a2 = str_to_number(item.split()[-1])
                        if a2 is not None:
                            self.summary['Ending Balance Savings'] = a2
                last_state = state
                state = 0

            for key in keywords.keys():
                if key in item:
                    last_state = state
                    state = keywords[key]
                    last_item = item

    def get_summary2(self, lst, debug=False):
        keywords = {
            'Previous Balance': 1,
            'Payments': 1,
            'Other Credits': 1,
            'Transactions': 1,
            'Cash Advances': 1,
            'Fees Charged': 1,
            'Interest Charged': 1,
            'New Balance': 1,
            'Credit Limit': 1,
            'Available Credit': 2,
            'Cash Advance Credit Limit': 1,
            'Available Credit for Cash Advances': 3,
            'Payment Due Date': 4,
            'days in Billing Cycle': 5
        }
        summary = {}
        last_key = ''
        state = 0
        for item in lst:
            for key in keywords.keys():
                if key in item:
                    state = keywords[key]
                    last_key = key

            if state == 0:
                pass
            elif state == 1:
                s2n = str_to_number(item.replace(last_key, ''))
                if s2n is not None:
                    summary[last_key] = s2n
                state = 0
            elif state == 2:
                s = item.replace(last_key, '').split(')')[1]
                s2n = str_to_number(s)
                if s2n is not None:
                    summary[last_key] = s2n
                state = 0
            elif state == 3:
                s = item.replace(last_key, '')
                s = s.replace('Payment Information', '')
                s2n = str_to_number(s)
                if s2n is not None:
                    summary[last_key] = s2n
                state = 0
            elif state == 4:
                # print(f'WTF do I do about {last_key} and {item}')
                state = 0
            elif state == 5:
                s = item.split(' | ')[0]
                s2d = str_to_date(s)
                if s2d is not None:
                    summary['Period Starting'] = s2d[0]
                    summary['Period Ending'] = s2d[1]
                state = 0

        summary['Account'] = self.account
        self.summary = summary

    def get_transactions(self, debug=False):
        lst = self.rawdata.split('\n')
        transactions = pd.DataFrame()
        state = 0
        next_entry = {}
        desc_buffer = ''
        for item in lst:
            s2d = str_to_date(item)
            s2n = str_to_number(item)

            if state == 0:
                pass
            elif state == 1:
                if item == 'Description':
                    state = 2
                else:
                    state = 0
            elif state == 2:
                if item == 'Amount':
                    state = 3
                else:
                    state = 0
            elif state == 3:
                if s2d is not None:
                    d = s2d[0]

                    if d.month == 1:
                        d = d.replace(year=self.summary['Period Ending'].year)
                    else:
                        d = d.replace(year=self.summary['Period Starting'].year)

                    next_entry['Date'] = d
                    state = 4
                else:
                    state = 3
            elif state == 4:
                if s2n is not None:
                    if '$' in item:
                        next_entry['Amount'] = s2n
                        next_entry['Description'] = desc_buffer
                        transactions = pd.concat([transactions, pd.DataFrame(next_entry, index=[0])], ignore_index=True)
                        desc_buffer = ''
                        next_entry = {}
                        state = 3
                    else:
                        desc_buffer = desc_buffer + item
                        state = 4
                else:
                    desc_buffer = desc_buffer + item
                    state = 4

            if item == "Date":
                state = 1
        if 'Period Ending' in self.summary.keys():
            transactions = pd.concat([transactions,
                                      pd.DataFrame({'Date': self.summary['Period Ending'],
                                                    'Description': 'Interest Charged',
                                                    'Amount': self.summary['Interest Charged']
                                                    }, index=[0])], ignore_index=True)
        transactions['Account'] = self.account
        transactions.Amount = transactions.Amount * -1
        self.transactions = transactions
        if debug:
            transactions.to_csv('D:\Artifacts\Test2.csv')

    def get_transactions2(self, lst, debug=False):
        transactions = pd.DataFrame()
        state = 0
        next_entry = {}
        for item in lst:
            if state == 0:
                pass
            elif state == 1:
                item = item.strip()
                cells = item.split(' ')
                if str_to_date(' '.join(cells[0:2])) is None:
                    continue
                t_date = ' '.join(cells[0:2])
                p_date = ' '.join(cells[2:4])
                if cells[-2] in ['+', '-']:
                    desc = ' '.join(cells[4:-2])
                    amt = ' '.join(cells[-2:])
                else:
                    desc = ' '.join(cells[4:-1])
                    amt = ' '.join(cells[-1:])

                t_date = str_to_date(t_date)[0]
                p_date = str_to_date(p_date)[0]
                amt = str_to_number(amt)

                if t_date.month == 1:
                    t_date = t_date.replace(year=self.summary['Period Ending'].year)
                else:
                    t_date = t_date.replace(year=self.summary['Period Starting'].year)
                if p_date.month == 1:
                    p_date = p_date.replace(year=self.summary['Period Ending'].year)
                else:
                    p_date = p_date.replace(year=self.summary['Period Starting'].year)

                new_entry = {
                    'Post Date': p_date,
                    'Transaction Date': t_date,
                    'Date': p_date,
                    'Amount': amt,
                    'Description': desc
                }
                if None in new_entry.values():
                    continue
                # elif np.isnan(new_entry['Date']):
                #     continue
                transactions = pd.concat([transactions,
                                          pd.DataFrame(new_entry, index=[0])], ignore_index=True)

            if item == "Trans Date Post Date Description Amount ":
                state = 1

        if 'Period Ending' in self.summary.keys():
            transactions = pd.concat([transactions,
                                      pd.DataFrame({'Date': self.summary['Period Ending'],
                                                    'Description': 'Interest Charged',
                                                    'Amount': self.summary['Interest Charged']
                                                    }, index=[0])], ignore_index=True)
        transactions['Account'] = self.account
        transactions.Amount = transactions.Amount * -1
        self.transactions = transactions
        if debug:
            transactions.to_csv('D:\Artifacts\Test2.csv')
