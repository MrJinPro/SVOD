/*
 Navicat Premium Data Transfer

 Source Server         : Pult4DB
 Source Server Type    : SQL Server
 Source Server Version : 14001000 (14.00.1000)
 Source Host           : 10.10.8.110:1433
 Source Catalog        : pult4db_archives
 Source Schema         : dbo

 Target Server Type    : SQL Server
 Target Server Version : 14001000 (14.00.1000)
 File Encoding         : 65001

 Date: 12/01/2026 07:47:23
*/


-- ----------------------------
-- Table structure for eventservice20260101
-- ----------------------------
IF EXISTS (SELECT * FROM sys.all_objects WHERE object_id = OBJECT_ID(N'[dbo].[eventservice20260101]') AND type IN ('U'))
	DROP TABLE [dbo].[eventservice20260101]
GO

CREATE TABLE [dbo].[eventservice20260101] (
  [Service_id] int  IDENTITY(1,1) NOT NULL,
  [NameState] nvarchar(60) COLLATE Cyrillic_General_CI_AS  NULL,
  [Event_id] int  NOT NULL,
  [Computer] nvarchar(50) COLLATE Cyrillic_General_CI_AS  NOT NULL,
  [OperationTime] datetime  NOT NULL,
  [Date_Key] int  NOT NULL,
  [PersonName] nvarchar(200) COLLATE Cyrillic_General_CI_AS  NULL,
  [GrResponseName] nvarchar(100) COLLATE Cyrillic_General_CI_AS  NULL
)
GO

ALTER TABLE [dbo].[eventservice20260101] SET (LOCK_ESCALATION = TABLE)
GO


-- ----------------------------
-- Auto increment value for eventservice20260101
-- ----------------------------
DBCC CHECKIDENT ('[dbo].[eventservice20260101]', RESEED, 65356)
GO


-- ----------------------------
-- Indexes structure for table eventservice20260101
-- ----------------------------
CREATE NONCLUSTERED INDEX [IX_eventservice20260101_ev_id_dt]
ON [dbo].[eventservice20260101] (
  [Event_id] ASC,
  [Date_Key] ASC
)
GO


-- ----------------------------
-- Checks structure for table eventservice20260101
-- ----------------------------
ALTER TABLE [dbo].[eventservice20260101] ADD CONSTRAINT [ck_eventservice20260101] CHECK ([Date_Key]>=(20260101) AND [Date_Key]<=(20260131))
GO


-- ----------------------------
-- Primary Key structure for table eventservice20260101
-- ----------------------------
ALTER TABLE [dbo].[eventservice20260101] ADD CONSTRAINT [pk_eventservice20260101] PRIMARY KEY CLUSTERED ([Service_id])
WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON)  
ON [PRIMARY]
GO


-- ----------------------------
-- Foreign Keys structure for table eventservice20260101
-- ----------------------------
ALTER TABLE [dbo].[eventservice20260101] ADD CONSTRAINT [fk_eventservice20260101_archive20260101] FOREIGN KEY ([Event_id]) REFERENCES [dbo].[archive20260101] ([Event_id]) ON DELETE NO ACTION ON UPDATE NO ACTION
GO

