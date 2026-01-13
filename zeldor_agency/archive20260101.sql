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

 Date: 12/01/2026 07:47:42
*/


-- ----------------------------
-- Table structure for archive20260101
-- ----------------------------
IF EXISTS (SELECT * FROM sys.all_objects WHERE object_id = OBJECT_ID(N'[dbo].[archive20260101]') AND type IN ('U'))
	DROP TABLE [dbo].[archive20260101]
GO

CREATE TABLE [dbo].[archive20260101] (
  [Event_id] int  NOT NULL,
  [Date_Key] int  NOT NULL,
  [Panel_id] varchar(15) COLLATE Cyrillic_General_CI_AS  NULL,
  [Group_] int  NULL,
  [Line] varchar(10) COLLATE Cyrillic_General_CI_AS  NULL,
  [Zone] int  NULL,
  [Code] varchar(6) COLLATE Cyrillic_General_CI_AS  NULL,
  [CodeGroup] smallint  NULL,
  [TimeEvent] datetime  NULL,
  [Phone] varchar(15) COLLATE Cyrillic_General_CI_AS  NULL,
  [MeterCount] nvarchar(300) COLLATE Cyrillic_General_CI_AS  NULL,
  [TimeMeterCount] datetime  NULL,
  [StateEvent] smallint  NULL,
  [Event_Parent_id] int  NULL,
  [Result_Text] nvarchar(800) COLLATE Cyrillic_General_CI_AS  NULL,
  [BitMask] int DEFAULT 0 NOT NULL,
  [DeviceEventTime] datetime  NULL,
  [ResultID] int  NULL
)
GO

ALTER TABLE [dbo].[archive20260101] SET (LOCK_ESCALATION = TABLE)
GO


-- ----------------------------
-- Indexes structure for table archive20260101
-- ----------------------------
CREATE NONCLUSTERED INDEX [archive20260101_date_key_Panel_id_TimeEvent]
ON [dbo].[archive20260101] (
  [Date_Key] ASC,
  [Panel_id] ASC,
  [TimeEvent] ASC
)
GO

CREATE NONCLUSTERED INDEX [IX_Linearchive20260101]
ON [dbo].[archive20260101] (
  [Panel_id] ASC,
  [Date_Key] ASC,
  [Line] ASC
)
INCLUDE ([Code])
GO


-- ----------------------------
-- Checks structure for table archive20260101
-- ----------------------------
ALTER TABLE [dbo].[archive20260101] ADD CONSTRAINT [ck_archive20260101] CHECK ([Date_Key]>=(20260101) AND [Date_Key]<=(20260131))
GO


-- ----------------------------
-- Primary Key structure for table archive20260101
-- ----------------------------
ALTER TABLE [dbo].[archive20260101] ADD CONSTRAINT [pk_archive20260101] PRIMARY KEY CLUSTERED ([Event_id])
WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON)  
ON [PRIMARY]
GO


-- ----------------------------
-- Foreign Keys structure for table archive20260101
-- ----------------------------
ALTER TABLE [dbo].[archive20260101] ADD CONSTRAINT [fk_archive20260101] FOREIGN KEY ([Event_Parent_id]) REFERENCES [dbo].[archive20260101] ([Event_id]) ON DELETE NO ACTION ON UPDATE NO ACTION
GO

