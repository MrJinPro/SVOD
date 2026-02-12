# Карта связей дампов агентства (по имеющимся .sql)

Источник скана: папка `zeldor_agency/`.
Скрипт: `backend/scripts/agency_schema_links.py`.
JSON-вывод: `backend/agency_schema_report.json`.

## Что уже есть (13 таблиц)
- `eventservice20260101` (действия операторов/ГБР по событиям)
- `archive20260101` (события: Panel_id, Group_, Code, TimeEvent, ...)
- `Panel` (карточка объекта/панели)
- `Groups` (группы на панели, привязка к Company)
- `Company`
- `Responsibles`, `ResponsiblesList`, `ResponsibleTel`
- `Code_T`, `States`, `Temp`, `Stands`, `EventsSendLog`

## Главная цепочка для рапортов (события → объект → клиент)
1) `eventservice20260101.Event_id` → FK на `archive20260101.Event_id`
2) `archive20260101.Panel_id + Group_` логически ведут к:
   - `Groups.Panel_id + Group_` (в `Responsibles` это FK подтверждён)
3) `Groups.Panel_id` → FK на `Panel.Panel_id`
4) `Groups.CompanyID` → FK на `Company.ID`
5) `Responsibles(panel_id, Group_)` → FK на `Groups(Panel_id, Group_)` (контакты/ответственные по объекту)

## Обнаруженные FK/REFERENCES (из ALTER TABLE)
- `eventservice20260101(Event_id)` → `archive20260101(Event_id)`
- `Groups(Panel_id)` → `Panel(Panel_id)`
- `Groups(CompanyID)` → `Company(ID)`
- `Responsibles(panel_id, Group_)` → `Groups(Panel_id, Group_)`
- `Responsibles(ResponsiblesList_id)` → `ResponsiblesList(ResponsiblesList_id)`
- `ResponsibleTel(ResponsiblesList_id)` → `ResponsiblesList(ResponsiblesList_id)`

## Какие таблицы точно «не хватает» (на них есть REFERENCES, но дампов нет)
Список сформирован автоматически из `REFERENCES [dbo].[X]`:
- `Areas`
- `CompanyType`
- `Customers`
- `Installers`
- `Masters`
- `MoreAboutLun7`
- `ResponsibleTypeTel`
- `ServiceOrganization`
- `TypeCode_T`
- `engineers`

## Про машины/экипажи ГБР
В текущих дампах нет ни одной таблицы/связи по машинам/ТС (не найдено `Car/Auto/Transport/Vehicle/NUMBER_CAR`).
Чтобы в рапортах было «какая машина / какой экипаж / какая группа выехала», нужны дампы таблиц, где хранится:
- справочник машин/ТС (номер машины, позывной, экипаж)
- справочник групп реагирования и их состав
- привязка «группа/машина/экипаж» к имени, которое попадает в `eventservice*.GrResponseName`

Практически: пришлите дампы любых таблиц, в названии которых есть `Car`, `Auto`, `Transport`, `Vehicle`, `Crew`, `Brigade`, `Response`, `GBR`, `Group*` (кроме уже имеющихся `Groups`).
