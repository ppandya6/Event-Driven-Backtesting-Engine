import csv
from datetime import datetime
from .models import Quote


def read_quotes(path):
    """Stream timezone-aware timestamp,symbol,bid,ask,size CSV rows."""
    with open(path, newline='', encoding='utf-8') as stream:
        for row in csv.DictReader(stream):
            yield Quote(datetime.fromisoformat(row['timestamp']), row['symbol'], row['bid'], row['ask'], int(row.get('size', 1000000)))
