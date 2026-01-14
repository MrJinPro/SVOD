/*
 Navicat Premium Data Transfer

 Source Server         : Pult4DB
 Source Server Type    : SQL Server
 Source Server Version : 14001000 (14.00.1000)
 Source Host           : 10.10.8.110:1433
 Source Catalog        : Pult4DB
 Source Schema         : dbo

 Target Server Type    : SQL Server
 Target Server Version : 14001000 (14.00.1000)
 File Encoding         : 65001

 Date: 14/01/2026 22:40:55
*/


-- ----------------------------
-- Table structure for Code_T
-- ----------------------------
IF EXISTS (SELECT * FROM sys.all_objects WHERE object_id = OBJECT_ID(N'[dbo].[Code_T]') AND type IN ('U'))
	DROP TABLE [dbo].[Code_T]
GO

CREATE TABLE [dbo].[Code_T] (
  [Code] varchar(6) COLLATE Cyrillic_General_CI_AS  NOT NULL,
  [CodeGroup] smallint  NOT NULL,
  [Message] nvarchar(500) COLLATE Cyrillic_General_CI_AS  NULL,
  [AutoReset] bit  NULL,
  [GroupSent] bit  NULL,
  [Flag] int  NULL,
  [Zoneno] int  NULL,
  [Svet] tinyint  NULL,
  [AccessCode] bit  NULL,
  [FileName] nvarchar(250) COLLATE Cyrillic_General_CI_AS  NULL,
  [idTCode] int  NULL,
  [System] bit DEFAULT 0 NULL,
  [IsNeedReport] bit  NULL,
  [contactId_code] varchar(4) COLLATE Cyrillic_General_CI_AS  NULL,
  [CodeMes_RU] nvarchar(4000) COLLATE Cyrillic_General_CI_AS  NULL,
  [CodeMes_EN] nvarchar(4000) COLLATE Cyrillic_General_CI_AS  NULL,
  [CodeMes_ES] nvarchar(4000) COLLATE Cyrillic_General_CI_AS  NULL,
  [CodeMes_UK] nvarchar(4000) COLLATE Cyrillic_General_CI_AS  NULL,
  [CodeMes_PL] nvarchar(4000) COLLATE Cyrillic_General_CI_AS  NULL,
  [CodeMes_FR] nvarchar(4000) COLLATE Cyrillic_General_CI_AS  NULL,
  [CodeMes_TR] nvarchar(4000) COLLATE Cyrillic_General_CI_AS  NULL,
  [CodeMes_LV] nvarchar(4000) COLLATE Cyrillic_General_CI_AS  NULL
)
GO

ALTER TABLE [dbo].[Code_T] SET (LOCK_ESCALATION = TABLE)
GO

EXEC sp_addextendedproperty
'MS_Description', N'Код',
'SCHEMA', N'dbo',
'TABLE', N'Code_T',
'COLUMN', N'Code'
GO

EXEC sp_addextendedproperty
'MS_Description', N'Набор кодов',
'SCHEMA', N'dbo',
'TABLE', N'Code_T',
'COLUMN', N'CodeGroup'
GO

EXEC sp_addextendedproperty
'MS_Description', N'Текстовое описание кода',
'SCHEMA', N'dbo',
'TABLE', N'Code_T',
'COLUMN', N'Message'
GO

EXEC sp_addextendedproperty
'MS_Description', N'1 - автосбрасываемое событие',
'SCHEMA', N'dbo',
'TABLE', N'Code_T',
'COLUMN', N'AutoReset'
GO

EXEC sp_addextendedproperty
'MS_Description', N'1 - Выезд группы реагирования',
'SCHEMA', N'dbo',
'TABLE', N'Code_T',
'COLUMN', N'GroupSent'
GO

EXEC sp_addextendedproperty
'MS_Description', N'Не используется',
'SCHEMA', N'dbo',
'TABLE', N'Code_T',
'COLUMN', N'Flag'
GO

EXEC sp_addextendedproperty
'MS_Description', N'Номер шлейфа',
'SCHEMA', N'dbo',
'TABLE', N'Code_T',
'COLUMN', N'Zoneno'
GO

EXEC sp_addextendedproperty
'MS_Description', N'Не используется',
'SCHEMA', N'dbo',
'TABLE', N'Code_T',
'COLUMN', N'Svet'
GO

EXEC sp_addextendedproperty
'MS_Description', N'1 - Является ключом доступа',
'SCHEMA', N'dbo',
'TABLE', N'Code_T',
'COLUMN', N'AccessCode'
GO

EXEC sp_addextendedproperty
'MS_Description', N'Имя звукового файла',
'SCHEMA', N'dbo',
'TABLE', N'Code_T',
'COLUMN', N'FileName'
GO

EXEC sp_addextendedproperty
'MS_Description', N'TypeCode.idTCode',
'SCHEMA', N'dbo',
'TABLE', N'Code_T',
'COLUMN', N'idTCode'
GO

EXEC sp_addextendedproperty
'MS_Description', N'1 - Системный код',
'SCHEMA', N'dbo',
'TABLE', N'Code_T',
'COLUMN', N'System'
GO

EXEC sp_addextendedproperty
'MS_Description', N'1 - Необходимость делать опрос объекта',
'SCHEMA', N'dbo',
'TABLE', N'Code_T',
'COLUMN', N'IsNeedReport'
GO

EXEC sp_addextendedproperty
'MS_Description', N'Код ContactID',
'SCHEMA', N'dbo',
'TABLE', N'Code_T',
'COLUMN', N'contactId_code'
GO


-- ----------------------------
-- Primary Key structure for table Code_T
-- ----------------------------
ALTER TABLE [dbo].[Code_T] ADD CONSTRAINT [PK_Code] PRIMARY KEY CLUSTERED ([Code], [CodeGroup])
WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON)  
ON [PRIMARY]
GO


-- ----------------------------
-- Foreign Keys structure for table Code_T
-- ----------------------------
ALTER TABLE [dbo].[Code_T] ADD CONSTRAINT [FK_Code_TypeCode] FOREIGN KEY ([idTCode]) REFERENCES [dbo].[TypeCode_T] ([idTCode]) ON DELETE CASCADE ON UPDATE CASCADE
GO

