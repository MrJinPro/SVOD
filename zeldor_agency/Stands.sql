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

 Date: 03/08/2025 22:54:15
*/


-- ----------------------------
-- Table structure for Stands
-- ----------------------------
IF EXISTS (SELECT * FROM sys.all_objects WHERE object_id = OBJECT_ID(N'[dbo].[Stands]') AND type IN ('U'))
	DROP TABLE [dbo].[Stands]
GO

CREATE TABLE [dbo].[Stands] (
  [id] int  IDENTITY(1,1) NOT FOR REPLICATION NOT NULL,
  [Panel_id] varchar(15) COLLATE Cyrillic_General_CI_AS  NOT NULL,
  [Group_] int  NULL,
  [Zone] int  NULL,
  [TimeBegin] datetime DEFAULT getdate() NULL,
  [TimeEnd] datetime  NULL,
  [Type_Stand] bit  NULL,
  [standorkey] tinyint  NULL,
  [Engineer_id] int  NULL
)
GO

ALTER TABLE [dbo].[Stands] SET (LOCK_ESCALATION = TABLE)
GO

EXEC sp_addextendedproperty
'MS_Description', N'ID',
'SCHEMA', N'dbo',
'TABLE', N'Stands',
'COLUMN', N'id'
GO

EXEC sp_addextendedproperty
'MS_Description', N'Groups.Panel_id',
'SCHEMA', N'dbo',
'TABLE', N'Stands',
'COLUMN', N'Panel_id'
GO

EXEC sp_addextendedproperty
'MS_Description', N'Groups.Group_',
'SCHEMA', N'dbo',
'TABLE', N'Stands',
'COLUMN', N'Group_'
GO

EXEC sp_addextendedproperty
'MS_Description', N'Шлейф',
'SCHEMA', N'dbo',
'TABLE', N'Stands',
'COLUMN', N'Zone'
GO

EXEC sp_addextendedproperty
'MS_Description', N'Начальное время',
'SCHEMA', N'dbo',
'TABLE', N'Stands',
'COLUMN', N'TimeBegin'
GO

EXEC sp_addextendedproperty
'MS_Description', N'Конечное время',
'SCHEMA', N'dbo',
'TABLE', N'Stands',
'COLUMN', N'TimeEnd'
GO

EXEC sp_addextendedproperty
'MS_Description', N'0 - временный; 1 - постоянный',
'SCHEMA', N'dbo',
'TABLE', N'Stands',
'COLUMN', N'Type_Stand'
GO

EXEC sp_addextendedproperty
'MS_Description', N'0 - стенд; 1- запрещенный ключ; 4 - игнорируемый.',
'SCHEMA', N'dbo',
'TABLE', N'Stands',
'COLUMN', N'standorkey'
GO

EXEC sp_addextendedproperty
'MS_Description', N'engineers.engineer_id',
'SCHEMA', N'dbo',
'TABLE', N'Stands',
'COLUMN', N'Engineer_id'
GO

EXEC sp_addextendedproperty
'MS_Description', N'Стенды/Запрещенные ключи/Игнорируемые',
'SCHEMA', N'dbo',
'TABLE', N'Stands'
GO


-- ----------------------------
-- Auto increment value for Stands
-- ----------------------------
DBCC CHECKIDENT ('[dbo].[Stands]', RESEED, 963348)
GO


-- ----------------------------
-- Primary Key structure for table Stands
-- ----------------------------
ALTER TABLE [dbo].[Stands] ADD CONSTRAINT [PK_Stands] PRIMARY KEY CLUSTERED ([id])
WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON)  
ON [PRIMARY]
GO


-- ----------------------------
-- Foreign Keys structure for table Stands
-- ----------------------------
ALTER TABLE [dbo].[Stands] ADD CONSTRAINT [FK_Stands_engineers] FOREIGN KEY ([Engineer_id]) REFERENCES [dbo].[engineers] ([engineer_id]) ON DELETE NO ACTION ON UPDATE NO ACTION
GO

