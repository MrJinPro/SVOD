#!/usr/bin/env python3
"""
Скрипт для генерации данных отчёта SVOD из SQL-дампов агентства.
Парсит eventservice20260201.sql и archive20260201.sql, склеивает по Event_id.
Вычисляет время пути ГБР (dispatch → arrival) и сохраняет результат в JSON.
"""

import argparse
import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

INSERT_LINE_RE = re.compile(
    r"INSERT\s+INTO\s+\[dbo\]\.\[(?P<table>[^\]]+)\]"
    r"\s*\((?P<cols>[^\)]+)\)\s*VALUES\s*\((?P<vals>.+)\)",
    flags=re.IGNORECASE,
)
VALUE_RE = re.compile(r"(?:N'(?P<str>(?:[^']|'')*)'|'(?P<str2>(?:[^']|'')*)'|NULL)", flags=re.IGNORECASE)


def open_text(path: Path):
    return path.open('r', encoding='utf-8', errors='replace')


def parse_insert_line(line: str, table_name: str) -> dict | None:
    match = INSERT_LINE_RE.search(line)
    if not match or match.group('table').lower() != table_name.lower():
        return None

    cols = [col.strip().strip('[]') for col in match.group('cols').split(',')]
    vals = []
    for value_match in VALUE_RE.finditer(match.group('vals')):
        raw = value_match.group('str') if value_match.group('str') is not None else value_match.group('str2')
        if raw is None:
            vals.append(None)
        else:
            vals.append(raw.replace("''", "'"))

    if len(cols) != len(vals):
        return None

    return dict(zip(cols, vals))


def parse_eventservice_rows(path: Path) -> list[dict]:
    rows = []
    with open_text(path) as f:
        for line in f:
            row = parse_insert_line(line, 'eventservice20260201')
            if row is not None:
                rows.append(row)
    return rows


def parse_archive_rows(path: Path, event_ids: set[str]) -> list[dict]:
    rows = []
    with open_text(path) as f:
        for line in f:
            row = parse_insert_line(line, 'archive20260201')
            if row is not None and row.get('Event_id') in event_ids:
                rows.append(row)
    return rows


def parse_datetime(value: str) -> datetime | None:
    if not value:
        return None
    for fmt in ('%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S'):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def build_report(event_rows: list[dict], archive_rows: list[dict]) -> list[dict]:
    event_data = defaultdict(lambda: {
        'operator': None,
        'gbr': None,
        'states': [],
        'dispatch_times': [],
        'arrival_times': [],
    })

    for row in event_rows:
        eid = row.get('Event_id')
        if not eid:
            continue

        state = row.get('NameState')
        op_time = parse_datetime(row.get('OperationTime') or '')
        if state:
            event_data[eid]['states'].append(state)
        if row.get('PersonName') and row['PersonName'].strip():
            if event_data[eid]['operator'] is None or event_data[eid]['operator'] == 'Система':
                event_data[eid]['operator'] = row['PersonName']
        if row.get('GrResponseName') and row['GrResponseName'].strip():
            event_data[eid]['gbr'] = row['GrResponseName']

        if op_time and state == 'Выслана группа реагирования':
            event_data[eid]['dispatch_times'].append(op_time)
        if op_time and state == 'Прибытие группы реагирования':
            event_data[eid]['arrival_times'].append(op_time)

    archive_by_event = {row['Event_id']: row for row in archive_rows if row.get('Event_id')}

    result = []
    for eid, data in event_data.items():
        archive = archive_by_event.get(eid)
        if not archive:
            continue

        dispatch_dt = min(data['dispatch_times']) if data['dispatch_times'] else None
        arrival_dt = None
        if data['arrival_times']:
            if dispatch_dt is not None:
                arrival_candidates = [dt for dt in data['arrival_times'] if dt >= dispatch_dt]
                arrival_dt = min(arrival_candidates) if arrival_candidates else min(data['arrival_times'])
            else:
                arrival_dt = min(data['arrival_times'])

        travel_time = None
        if dispatch_dt and arrival_dt:
            travel_time = (arrival_dt - dispatch_dt).total_seconds()

        result.append({
            'event_id': eid,
            'operator': data['operator'],
            'gbr': data['gbr'],
            'dispatch_time': dispatch_dt.isoformat() if dispatch_dt else None,
            'arrival_time': arrival_dt.isoformat() if arrival_dt else None,
            'travel_time_seconds': travel_time,
            'panel_id': archive.get('Panel_id'),
            'line': archive.get('Line'),
            'zone': archive.get('Zone'),
            'code': archive.get('Code'),
            'time_event': archive.get('TimeEvent'),
            'meter_count': archive.get('MeterCount'),
            'result_text': archive.get('Result_Text'),
            'state_event': archive.get('StateEvent'),
            'date_key': archive.get('Date_Key'),
            'group': archive.get('Group_'),
            'event_parent_id': archive.get('Event_Parent_id'),
            'states': data['states'],
        })

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description='Generate SVOD report data from agency SQL dumps.')
    parser.add_argument('--eventservice', default=None, help='Path to eventservice20260201.sql')
    parser.add_argument('--archive', default=None, help='Path to archive20260201.sql')
    parser.add_argument('--output', default=None, help='Path to output JSON file')
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[2]
    dump_dir = Path(args.eventservice or root / 'damp_db_agency')
    eventservice_path = Path(args.eventservice or dump_dir / 'eventservice20260201.sql')
    archive_path = Path(args.archive or dump_dir / 'archive20260201.sql')
    output_path = Path(args.output or Path(__file__).parent / 'report_data.json')

    if not eventservice_path.exists():
        print(f'Eventservice file not found: {eventservice_path}')
        return 1
    if not archive_path.exists():
        print(f'Archive file not found: {archive_path}')
        return 1

    print(f'Parsing eventservice file: {eventservice_path}')
    event_rows = parse_eventservice_rows(eventservice_path)
    event_ids = {row['Event_id'] for row in event_rows if row.get('Event_id')}
    print(f'Found {len(event_rows)} eventservice rows, {len(event_ids)} unique Event_id')

    print(f'Parsing archive file: {archive_path}')
    archive_rows = parse_archive_rows(archive_path, event_ids)
    print(f'Found {len(archive_rows)} archive rows matching Event_id from eventservice')

    report_data = build_report(event_rows, archive_rows)
    print(f'Built {len(report_data)} report records')

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open('w', encoding='utf-8') as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)

    print(f'Report data saved to: {output_path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
