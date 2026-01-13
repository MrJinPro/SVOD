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

 Date: 11/09/2024 01:42:41
*/


-- ----------------------------
-- Table structure for ResponsiblesList
-- ----------------------------
IF EXISTS (SELECT * FROM sys.all_objects WHERE object_id = OBJECT_ID(N'[dbo].[ResponsiblesList]') AND type IN ('U'))
	DROP TABLE [dbo].[ResponsiblesList]
GO

CREATE TABLE [dbo].[ResponsiblesList] (
  [ResponsiblesList_id] int  IDENTITY(1,1) NOT FOR REPLICATION NOT NULL,
  [Responsible_Name] nvarchar(100) COLLATE Cyrillic_General_CI_AS  NOT NULL,
  [Responsible_Address] nvarchar(500) COLLATE Cyrillic_General_CI_AS  NULL,
  [panel_id_AD] varchar(15) COLLATE Cyrillic_General_CI_AS  NULL,
  [RespMerge_ID] int  NULL
)
GO

ALTER TABLE [dbo].[ResponsiblesList] SET (LOCK_ESCALATION = TABLE)
GO


-- ----------------------------
-- Auto increment value for ResponsiblesList
-- ----------------------------
DBCC CHECKIDENT ('[dbo].[ResponsiblesList]', RESEED, 124079)
GO


-- ----------------------------
-- Primary Key structure for table ResponsiblesList
-- ----------------------------
ALTER TABLE [dbo].[ResponsiblesList] ADD CONSTRAINT [pk_ResponsiblesList] PRIMARY KEY CLUSTERED ([ResponsiblesList_id])
WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON)  
ON [PRIMARY]
GO

