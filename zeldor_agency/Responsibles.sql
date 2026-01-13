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

 Date: 18/08/2024 21:02:28
*/


-- ----------------------------
-- Table structure for Responsibles
-- ----------------------------
IF EXISTS (SELECT * FROM sys.all_objects WHERE object_id = OBJECT_ID(N'[dbo].[Responsibles]') AND type IN ('U'))
	DROP TABLE [dbo].[Responsibles]
GO

CREATE TABLE [dbo].[Responsibles] (
  [Responsible_id] int  IDENTITY(1,1) NOT FOR REPLICATION NOT NULL,
  [panel_id] varchar(15) COLLATE Cyrillic_General_CI_AS  NOT NULL,
  [Group_] int  NOT NULL,
  [Responsible_Number] int  NOT NULL,
  [ResponsiblesList_id] int  NOT NULL,
  [panel_id_AD] varchar(15) COLLATE Cyrillic_General_CI_AS  NULL,
  [RespMerge_ID] int  NULL
)
GO

ALTER TABLE [dbo].[Responsibles] SET (LOCK_ESCALATION = TABLE)
GO

EXEC sp_addextendedproperty
'MS_Description', N'ID',
'SCHEMA', N'dbo',
'TABLE', N'Responsibles',
'COLUMN', N'Responsible_id'
GO

EXEC sp_addextendedproperty
'MS_Description', N'Groups.Panel_id',
'SCHEMA', N'dbo',
'TABLE', N'Responsibles',
'COLUMN', N'panel_id'
GO

EXEC sp_addextendedproperty
'MS_Description', N'Groups.Group_',
'SCHEMA', N'dbo',
'TABLE', N'Responsibles',
'COLUMN', N'Group_'
GO

EXEC sp_addextendedproperty
'MS_Description', N'Порядковый номер',
'SCHEMA', N'dbo',
'TABLE', N'Responsibles',
'COLUMN', N'Responsible_Number'
GO

EXEC sp_addextendedproperty
'MS_Description', N'Ответственные лица',
'SCHEMA', N'dbo',
'TABLE', N'Responsibles'
GO


-- ----------------------------
-- Auto increment value for Responsibles
-- ----------------------------
DBCC CHECKIDENT ('[dbo].[Responsibles]', RESEED, 1289399)
GO


-- ----------------------------
-- Indexes structure for table Responsibles
-- ----------------------------
CREATE NONCLUSTERED INDEX [IX_Responsibles_PanelID_Group]
ON [dbo].[Responsibles] (
  [panel_id] ASC,
  [Group_] ASC
)
GO

CREATE NONCLUSTERED INDEX [IX_Responsibles_ResponsiblesList_id]
ON [dbo].[Responsibles] (
  [ResponsiblesList_id] ASC
)
GO


-- ----------------------------
-- Uniques structure for table Responsibles
-- ----------------------------
ALTER TABLE [dbo].[Responsibles] ADD CONSTRAINT [UQ_Responsibles_List_Object] UNIQUE NONCLUSTERED ([panel_id] ASC, [Group_] ASC, [ResponsiblesList_id] ASC)
WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON)  
ON [PRIMARY]
GO


-- ----------------------------
-- Primary Key structure for table Responsibles
-- ----------------------------
ALTER TABLE [dbo].[Responsibles] ADD CONSTRAINT [PK__Responsibles__0F582957] PRIMARY KEY CLUSTERED ([Responsible_id])
WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON)  
ON [PRIMARY]
GO


-- ----------------------------
-- Foreign Keys structure for table Responsibles
-- ----------------------------
ALTER TABLE [dbo].[Responsibles] ADD CONSTRAINT [FK_Responsibles_ResponsiblesList] FOREIGN KEY ([ResponsiblesList_id]) REFERENCES [dbo].[ResponsiblesList] ([ResponsiblesList_id]) ON DELETE CASCADE ON UPDATE CASCADE
GO

ALTER TABLE [dbo].[Responsibles] ADD CONSTRAINT [FK_Responsibles_Groups] FOREIGN KEY ([panel_id], [Group_]) REFERENCES [dbo].[Groups] ([Panel_id], [Group_]) ON DELETE CASCADE ON UPDATE CASCADE
GO

