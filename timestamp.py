from datetime import datetime

def get_timestamp_log():
    date = datetime.now()
    return date.strftime("%H:%M:%S")+f".{date.microsecond//1000:03d}"

def get_timestamp_tx():
    date = datetime.now()
    unix_timestamp = date.timestamp()
    return unix_timestamp