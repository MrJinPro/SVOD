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

 Date: 11/09/2024 01:43:00
*/


-- ----------------------------
-- Table structure for ResponsibleTel
-- ----------------------------
IF EXISTS (SELECT * FROM sys.all_objects WHERE object_id = OBJECT_ID(N'[dbo].[ResponsibleTel]') AND type IN ('U'))
	DROP TABLE [dbo].[ResponsibleTel]
GO

CREATE TABLE [dbo].[ResponsibleTel] (
  [PhoneNo] varchar(25) COLLATE Cyrillic_General_CI_AS  NOT NULL,
  [TypeTel_id] smallint  NULL,
  [ResponsiblesList_id] int  NOT NULL,
  [ResponsibleTel_id] int  IDENTITY(1,1) NOT FOR REPLICATION NOT NULL
)
GO

ALTER TABLE [dbo].[ResponsibleTel] SET (LOCK_ESCALATION = TABLE)
GO

EXEC sp_addextendedproperty
'MS_Description', N'Номер телефона',
'SCHEMA', N'dbo',
'TABLE', N'ResponsibleTel',
'COLUMN', N'PhoneNo'
GO

EXEC sp_addextendedproperty
'MS_Description', N'ResponsibleTypeTel.TypeTel_id',
'SCHEMA', N'dbo',
'TABLE', N'ResponsibleTel',
'COLUMN', N'TypeTel_id'
GO

EXEC sp_addextendedproperty
'MS_Description', N'Список телефонов ответственного лица',
'SCHEMA', N'dbo',
'TABLE', N'ResponsibleTel'
GO


-- ----------------------------
-- Auto increment value for ResponsibleTel
-- ----------------------------
DBCC CHECKIDENT ('[dbo].[ResponsibleTel]', RESEED, 153362)
GO


-- ----------------------------
-- Indexes structure for table ResponsibleTel
-- ----------------------------
CREATE NONCLUSTERED INDEX [IX_ResponsibleTel_ResponsiblesList_id]
ON [dbo].[ResponsibleTel] (
  [ResponsiblesList_id] ASC
)
GO

CREATE NONCLUSTERED INDEX [IX_ResponsibleTel_PhoneNo]
ON [dbo].[ResponsibleTel] (
  [PhoneNo] ASC
)
GO


-- ----------------------------
-- Primary Key structure for table ResponsibleTel
-- ----------------------------
ALTER TABLE [dbo].[ResponsibleTel] ADD CONSTRAINT [PK_Responsible_Tel] PRIMARY KEY CLUSTERED ([ResponsibleTel_id])
WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON)  
ON [PRIMARY]
GO


-- ----------------------------
-- Foreign Keys structure for table ResponsibleTel
-- ----------------------------
ALTER TABLE [dbo].[ResponsibleTel] ADD CONSTRAINT [FK_ResponsibleTel_ResponsiblesList] FOREIGN KEY ([ResponsiblesList_id]) REFERENCES [dbo].[ResponsiblesList] ([ResponsiblesList_id]) ON DELETE CASCADE ON UPDATE CASCADE
GO

ALTER TABLE [dbo].[ResponsibleTel] ADD CONSTRAINT [FK_ResponsibleTel_ResponsibleTypeTel] FOREIGN KEY ([TypeTel_id]) REFERENCES [dbo].[ResponsibleTypeTel] ([TypeTel_id]) ON DELETE NO ACTION ON UPDATE NO ACTION
GO

