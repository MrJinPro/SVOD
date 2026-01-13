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

 Date: 18/08/2024 21:00:28
*/


-- ----------------------------
-- Table structure for Temp
-- ----------------------------
IF EXISTS (SELECT * FROM sys.all_objects WHERE object_id = OBJECT_ID(N'[dbo].[Temp]') AND type IN ('U'))
	DROP TABLE [dbo].[Temp]
GO

CREATE TABLE [dbo].[Temp] (
  [Event_id] int  NOT NULL,
  [Panel_id] varchar(15) COLLATE Cyrillic_General_CI_AS  NULL,
  [Group_] int  NULL,
  [Line] varchar(10) COLLATE Cyrillic_General_CI_AS  NULL,
  [Zone] int  NULL,
  [Code] varchar(6) COLLATE Cyrillic_General_CI_AS  NULL,
  [CodeGroup] smallint  NULL,
  [TimeEvent] datetime  NULL,
  [Receiver] int  NULL,
  [Phone] varchar(15) COLLATE Cyrillic_General_CI_AS  NULL,
  [MeterCount] nvarchar(300) COLLATE Cyrillic_General_CI_AS  NULL,
  [StateEvent] smallint  NULL,
  [Event_Parent_id] int  NULL,
  [Date_Key] int  NOT NULL,
  [Priority] int  NULL,
  [Computer] nvarchar(250) COLLATE Cyrillic_General_CI_AS  NULL,
  [BitMask] int DEFAULT 0 NOT NULL,
  [DeviceEventTime] datetime  NULL
)
GO

ALTER TABLE [dbo].[Temp] SET (LOCK_ESCALATION = TABLE)
GO


-- ----------------------------
-- Primary Key structure for table Temp
-- ----------------------------
ALTER TABLE [dbo].[Temp] ADD CONSTRAINT [pk_Temp] PRIMARY KEY CLUSTERED ([Event_id])
WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON)  
ON [PRIMARY]
GO


-- ----------------------------
-- Foreign Keys structure for table Temp
-- ----------------------------
ALTER TABLE [dbo].[Temp] ADD CONSTRAINT [fk_Temp] FOREIGN KEY ([Event_Parent_id]) REFERENCES [dbo].[Temp] ([Event_id]) ON DELETE NO ACTION ON UPDATE NO ACTION
GO

