/*
 Navicat Premium Data Transfer

 Source Server         : PHOENIX
 Source Server Type    : SQL Server
 Source Server Version : 14001000 (14.00.1000)
 Source Host           : 127.0.0.1:1433
 Source Catalog        : Pult4DB
 Source Schema         : dbo

 Target Server Type    : SQL Server
 Target Server Version : 14001000 (14.00.1000)
 File Encoding         : 65001

 Date: 03/08/2025 22:53:33
*/


-- ----------------------------
-- Table structure for Groups
-- ----------------------------
IF EXISTS (SELECT * FROM sys.all_objects WHERE object_id = OBJECT_ID(N'[dbo].[Groups]') AND type IN ('U'))
	DROP TABLE [dbo].[Groups]
GO

CREATE TABLE [dbo].[Groups] (
  [Panel_id] varchar(15) COLLATE Cyrillic_General_CI_AS  NOT NULL,
  [Group_] int  NOT NULL,
  [Message] nvarchar(100) COLLATE Cyrillic_General_CI_AS  NOT NULL,
  [IsOpen] bit  NULL,
  [TimeEvent] datetime  NULL,
  [OpenControl] bit  NULL,
  [Z8Timeout] datetime  NULL,
  [info_id] int  NULL,
  [typeSchedule] int  NULL,
  [ArmedCall] bit  NULL,
  [disabled] bit  NULL,
  [mustCall] bit  NULL,
  [TimeForClose] datetime  NULL,
  [Partial] nvarchar(150) COLLATE Cyrillic_General_CI_AS  NULL,
  [OperatorPrompt] nvarchar(2000) COLLATE Cyrillic_General_CI_AS  NULL,
  [IsProhibited] bit  NULL,
  [AutoArmDisarm] bit DEFAULT 0 NOT NULL,
  [alarmButtonPhMk] bit DEFAULT 0 NOT NULL,
  [IsOpenByAccess] bit  NULL,
  [IntervalPatrolInspection] datetime  NULL,
  [CompanyID] int  NULL
)
GO

ALTER TABLE [dbo].[Groups] SET (LOCK_ESCALATION = TABLE)
GO

EXEC sp_addextendedproperty
'MS_Description', N'Panel.Panel_id',
'SCHEMA', N'dbo',
'TABLE', N'Groups',
'COLUMN', N'Panel_id'
GO

EXEC sp_addextendedproperty
'MS_Description', N'Номер',
'SCHEMA', N'dbo',
'TABLE', N'Groups',
'COLUMN', N'Group_'
GO

EXEC sp_addextendedproperty
'MS_Description', N'Описание',
'SCHEMA', N'dbo',
'TABLE', N'Groups',
'COLUMN', N'Message'
GO

EXEC sp_addextendedproperty
'MS_Description', N'Группа под охраной: 0 - да; 1 - нет',
'SCHEMA', N'dbo',
'TABLE', N'Groups',
'COLUMN', N'IsOpen'
GO

EXEC sp_addextendedproperty
'MS_Description', N'Время прихода последнего события',
'SCHEMA', N'dbo',
'TABLE', N'Groups',
'COLUMN', N'TimeEvent'
GO

EXEC sp_addextendedproperty
'MS_Description', N'1 - Контроль открытий по расписанию',
'SCHEMA', N'dbo',
'TABLE', N'Groups',
'COLUMN', N'OpenControl'
GO

EXEC sp_addextendedproperty
'MS_Description', N'Ожидание звонка с объекта при открытии в течении ЧЧ:ММ',
'SCHEMA', N'dbo',
'TABLE', N'Groups',
'COLUMN', N'Z8Timeout'
GO

EXEC sp_addextendedproperty
'MS_Description', N'MoreAboutLun7.info_id',
'SCHEMA', N'dbo',
'TABLE', N'Groups',
'COLUMN', N'info_id'
GO

EXEC sp_addextendedproperty
'MS_Description', N'Тип работы группы: 1 - свободный график работы; 2 ->  круглосуточно под охраной; 3 - постановки и снятия отсутствуют (только тревожная кнопка); 4 - индивидуальное расписание; 5 - неизвестно',
'SCHEMA', N'dbo',
'TABLE', N'Groups',
'COLUMN', N'typeSchedule'
GO

EXEC sp_addextendedproperty
'MS_Description', N'Ставятся под охрану по звонку: 1 - да; 0 - нет (не используется)',
'SCHEMA', N'dbo',
'TABLE', N'Groups',
'COLUMN', N'ArmedCall'
GO

EXEC sp_addextendedproperty
'MS_Description', N'Группа отключена',
'SCHEMA', N'dbo',
'TABLE', N'Groups',
'COLUMN', N'disabled'
GO

EXEC sp_addextendedproperty
'MS_Description', N'Обязательный прозвон, при нарушении режима работы',
'SCHEMA', N'dbo',
'TABLE', N'Groups',
'COLUMN', N'mustCall'
GO

EXEC sp_addextendedproperty
'MS_Description', N'Контроль закрытий круглосуточных объектов, интервал ЧЧ:ММ',
'SCHEMA', N'dbo',
'TABLE', N'Groups',
'COLUMN', N'TimeForClose'
GO

EXEC sp_addextendedproperty
'MS_Description', N'Не используется',
'SCHEMA', N'dbo',
'TABLE', N'Groups',
'COLUMN', N'Partial'
GO

EXEC sp_addextendedproperty
'MS_Description', N'Инструкция по реагированию для оператора',
'SCHEMA', N'dbo',
'TABLE', N'Groups',
'COLUMN', N'OperatorPrompt'
GO

EXEC sp_addextendedproperty
'MS_Description', N'Признак запрет постановки для группы (с приборами Лунь-11,15): 1 - да; 0 - нет',
'SCHEMA', N'dbo',
'TABLE', N'Groups',
'COLUMN', N'IsProhibited'
GO

EXEC sp_addextendedproperty
'MS_Description', N'Группы объекта',
'SCHEMA', N'dbo',
'TABLE', N'Groups'
GO


-- ----------------------------
-- Triggers structure for table Groups
-- ----------------------------
CREATE TRIGGER [dbo].[DELCOMPANY]
ON [dbo].[Groups]
WITH EXECUTE AS CALLER
FOR DELETE
AS
BEGIN
if (select count(company_id) from Groups where company_id
 in (select distinct company_id from deleted)) = 0
delete from company where company_id in
(select distinct company_id from deleted)
END
GO

DISABLE TRIGGER [dbo].[DELCOMPANY] ON [dbo].[Groups]
GO


-- ----------------------------
-- Primary Key structure for table Groups
-- ----------------------------
ALTER TABLE [dbo].[Groups] ADD CONSTRAINT [pk_Group] PRIMARY KEY CLUSTERED ([Panel_id], [Group_])
WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON)  
ON [PRIMARY]
GO


-- ----------------------------
-- Foreign Keys structure for table Groups
-- ----------------------------
ALTER TABLE [dbo].[Groups] ADD CONSTRAINT [fk_moreInfo] FOREIGN KEY ([info_id]) REFERENCES [dbo].[MoreAboutLun7] ([info_id]) ON DELETE SET NULL ON UPDATE CASCADE
GO

ALTER TABLE [dbo].[Groups] ADD CONSTRAINT [fk_PanelG] FOREIGN KEY ([Panel_id]) REFERENCES [dbo].[Panel] ([Panel_id]) ON DELETE CASCADE ON UPDATE CASCADE
GO

ALTER TABLE [dbo].[Groups] ADD CONSTRAINT [fk_Company] FOREIGN KEY ([CompanyID]) REFERENCES [dbo].[Company] ([ID]) ON DELETE NO ACTION ON UPDATE CASCADE
GO

