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

 Date: 14/01/2025 14:50:26
*/


-- ----------------------------
-- Table structure for States
-- ----------------------------
IF EXISTS (SELECT * FROM sys.all_objects WHERE object_id = OBJECT_ID(N'[dbo].[States]') AND type IN ('U'))
	DROP TABLE [dbo].[States]
GO

CREATE TABLE [dbo].[States] (
  [State_id] int  IDENTITY(1,1) NOT FOR REPLICATION NOT NULL,
  [StateName] nvarchar(60) COLLATE Cyrillic_General_CI_AS  NOT NULL,
  [isOverProcess] bit DEFAULT 0 NOT NULL,
  [IsChangeStateEvent] bit DEFAULT 1 NOT NULL
)
GO

ALTER TABLE [dbo].[States] SET (LOCK_ESCALATION = TABLE)
GO

EXEC sp_addextendedproperty
'MS_Description', N'ID',
'SCHEMA', N'dbo',
'TABLE', N'States',
'COLUMN', N'State_id'
GO

EXEC sp_addextendedproperty
'MS_Description', N'Наименование',
'SCHEMA', N'dbo',
'TABLE', N'States',
'COLUMN', N'StateName'
GO

EXEC sp_addextendedproperty
'MS_Description', N'1 - завершение обработки',
'SCHEMA', N'dbo',
'TABLE', N'States',
'COLUMN', N'isOverProcess'
GO

EXEC sp_addextendedproperty
'MS_Description', N'1 - изменение состояния',
'SCHEMA', N'dbo',
'TABLE', N'States',
'COLUMN', N'IsChangeStateEvent'
GO

EXEC sp_addextendedproperty
'MS_Description', N'Список доступных операций для данного события',
'SCHEMA', N'dbo',
'TABLE', N'States'
GO


-- ----------------------------
-- Records of States
-- ----------------------------
SET IDENTITY_INSERT [dbo].[States] ON
GO

INSERT INTO [dbo].[States] ([State_id], [StateName], [isOverProcess], [IsChangeStateEvent]) VALUES (N'1', N'Прием на обработку', N'0', N'1')
GO

INSERT INTO [dbo].[States] ([State_id], [StateName], [isOverProcess], [IsChangeStateEvent]) VALUES (N'2', N'Выслана группа реагирования', N'0', N'1')
GO

INSERT INTO [dbo].[States] ([State_id], [StateName], [isOverProcess], [IsChangeStateEvent]) VALUES (N'3', N'Прибытие группы реагирования', N'0', N'1')
GO

INSERT INTO [dbo].[States] ([State_id], [StateName], [isOverProcess], [IsChangeStateEvent]) VALUES (N'4', N'Окончание обработки', N'1', N'1')
GO

INSERT INTO [dbo].[States] ([State_id], [StateName], [isOverProcess], [IsChangeStateEvent]) VALUES (N'5', N'Перехват события', N'0', N'0')
GO

INSERT INTO [dbo].[States] ([State_id], [StateName], [isOverProcess], [IsChangeStateEvent]) VALUES (N'6', N'Объект переведен в стенды', N'1', N'1')
GO

INSERT INTO [dbo].[States] ([State_id], [StateName], [isOverProcess], [IsChangeStateEvent]) VALUES (N'7', N'Отмена вызова группы реагирования', N'0', N'0')
GO

INSERT INTO [dbo].[States] ([State_id], [StateName], [isOverProcess], [IsChangeStateEvent]) VALUES (N'8', N'Отмена тревоги', N'1', N'1')
GO

INSERT INTO [dbo].[States] ([State_id], [StateName], [isOverProcess], [IsChangeStateEvent]) VALUES (N'9', N'Патруль', N'0', N'0')
GO

INSERT INTO [dbo].[States] ([State_id], [StateName], [isOverProcess], [IsChangeStateEvent]) VALUES (N'10', N'Включение зажигания', N'0', N'0')
GO

INSERT INTO [dbo].[States] ([State_id], [StateName], [isOverProcess], [IsChangeStateEvent]) VALUES (N'11', N'Выключение зажигания', N'0', N'0')
GO

INSERT INTO [dbo].[States] ([State_id], [StateName], [isOverProcess], [IsChangeStateEvent]) VALUES (N'12', N'Перезапуск Орлан-GPRS', N'1', N'1')
GO

INSERT INTO [dbo].[States] ([State_id], [StateName], [isOverProcess], [IsChangeStateEvent]) VALUES (N'13', N'Обработка нового дополнительного события', N'0', N'0')
GO

INSERT INTO [dbo].[States] ([State_id], [StateName], [isOverProcess], [IsChangeStateEvent]) VALUES (N'14', N'Оповещение ответственных лиц', N'0', N'0')
GO

INSERT INTO [dbo].[States] ([State_id], [StateName], [isOverProcess], [IsChangeStateEvent]) VALUES (N'15', N'Пересылка по Contact-ID', N'0', N'0')
GO

SET IDENTITY_INSERT [dbo].[States] OFF
GO


-- ----------------------------
-- Auto increment value for States
-- ----------------------------
DBCC CHECKIDENT ('[dbo].[States]', RESEED, 15)
GO


-- ----------------------------
-- Primary Key structure for table States
-- ----------------------------
ALTER TABLE [dbo].[States] ADD CONSTRAINT [PK__Operations__1CBC4616] PRIMARY KEY CLUSTERED ([State_id])
WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON)  
ON [PRIMARY]
GO

