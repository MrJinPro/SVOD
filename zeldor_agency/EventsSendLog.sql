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

 Date: 30/07/2025 17:12:37
*/


-- ----------------------------
-- Table structure for EventsSendLog
-- ----------------------------
IF EXISTS (SELECT * FROM sys.all_objects WHERE object_id = OBJECT_ID(N'[dbo].[EventsSendLog]') AND type IN ('U'))
	DROP TABLE [dbo].[EventsSendLog]
GO

CREATE TABLE [dbo].[EventsSendLog] (
  [log_id] int  IDENTITY(1,1) NOT FOR REPLICATION NOT NULL,
  [LogType_id] int  NOT NULL,
  [Panel_id] varchar(15) COLLATE Cyrillic_General_CI_AS  NULL,
  [Group_] int  NULL,
  [Zone] int  NULL,
  [Code] varchar(6) COLLATE Cyrillic_General_CI_AS  NULL,
  [CodeGroup] int  NULL,
  [DateTimeSend] datetime  NULL,
  [DateTimeRecived] datetime  NULL,
  [result] tinyint  NULL,
  [MeterCount] varchar(50) COLLATE Cyrillic_General_CI_AS  NULL,
  [TextSMS] nvarchar(1000) COLLATE Cyrillic_General_CI_AS  NULL,
  [AddressRemotePult] varchar(15) COLLATE Cyrillic_General_CI_AS  NULL,
  [TimePutWebServerEvent] datetime  NULL
)
GO

ALTER TABLE [dbo].[EventsSendLog] SET (LOCK_ESCALATION = TABLE)
GO


-- ----------------------------
-- Auto increment value for EventsSendLog
-- ----------------------------
DBCC CHECKIDENT ('[dbo].[EventsSendLog]', RESEED, 2044491)
GO


-- ----------------------------
-- Primary Key structure for table EventsSendLog
-- ----------------------------
ALTER TABLE [dbo].[EventsSendLog] ADD CONSTRAINT [PK__EventsSendLog__520F23F5] PRIMARY KEY CLUSTERED ([log_id])
WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON)  
ON [PRIMARY]
GO

