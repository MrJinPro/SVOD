/*
 Navicat Premium Data Transfer

 Source Server         : PHOENIX
 Source Server Type    : SQL Server
 Source Server Version : 14001000 (14.00.1000)
 Source Host           : 10.10.8.110:1433
 Source Catalog        : Pult4DB
 Source Schema         : dbo

 Target Server Type    : SQL Server
 Target Server Version : 14001000 (14.00.1000)
 File Encoding         : 65001

 Date: 23/06/2025 08:40:07
*/


-- ----------------------------
-- Table structure for Panel
-- ----------------------------
IF EXISTS (SELECT * FROM sys.all_objects WHERE object_id = OBJECT_ID(N'[dbo].[Panel]') AND type IN ('U'))
	DROP TABLE [dbo].[Panel]
GO

CREATE TABLE [dbo].[Panel] (
  [Panel_id] varchar(15) COLLATE Cyrillic_General_CI_AS  NOT NULL,
  [Password_] varchar(12) COLLATE Cyrillic_General_CI_AS  NULL,
  [CreateDate] datetime DEFAULT getdate() NULL,
  [Disabled] bit  NOT NULL,
  [Remarks] nvarchar(100) COLLATE Cyrillic_General_CI_AS  NULL,
  [computer] nvarchar(50) COLLATE Cyrillic_General_CI_AS  NULL,
  [DateLastChange] datetime  NULL,
  [engineer_id] int  NULL,
  [Area_id] int  NULL,
  [AdditionalTechnicalInformation] nvarchar(2000) COLLATE Cyrillic_General_CI_AS  NULL,
  [OneTestEqualAll] bit DEFAULT 0 NOT NULL,
  [master_id] int  NULL,
  [installer_id] int  NULL,
  [CompEditing] nvarchar(20) COLLATE Cyrillic_General_CI_AS DEFAULT NULL NULL,
  [TestPanel] bit DEFAULT 0 NOT NULL,
  [Partial] nvarchar(500) COLLATE Cyrillic_General_CI_AS  NULL,
  [Latitude] varchar(20) COLLATE Cyrillic_General_CI_AS  NULL,
  [Longtitude] varchar(20) COLLATE Cyrillic_General_CI_AS  NULL,
  [isGPSConfirm] bit DEFAULT 0 NOT NULL,
  [CompLastEditGPS] nvarchar(70) COLLATE Cyrillic_General_CI_AS  NULL,
  [Engine] bit DEFAULT 0 NOT NULL,
  [Track] int DEFAULT 0 NOT NULL,
  [isAlwaysSendGPS] bit DEFAULT 1 NOT NULL,
  [Movable_Object] bit DEFAULT 0 NOT NULL,
  [Panel_type] smallint DEFAULT 0 NOT NULL,
  [Pult_id] int  NULL,
  [UserName] nvarchar(200) COLLATE Cyrillic_General_CI_AS  NULL,
  [RegionID] int  NULL,
  [IsContactIDRedirect] bit DEFAULT 1 NOT NULL,
  [ContactIDObjectNumber] varchar(15) COLLATE Cyrillic_General_CI_AS  NULL,
  [TechPanel] bit DEFAULT 0 NOT NULL,
  [IsUseCameras] bit DEFAULT 0 NOT NULL,
  [ObjectID] int  IDENTITY(1,1) NOT FOR REPLICATION NOT NULL
)
GO

ALTER TABLE [dbo].[Panel] SET (LOCK_ESCALATION = TABLE)
GO

EXEC sp_addextendedproperty
'MS_Description', N'Номер объекта',
'SCHEMA', N'dbo',
'TABLE', N'Panel',
'COLUMN', N'Panel_id'
GO

EXEC sp_addextendedproperty
'MS_Description', N'Пароль',
'SCHEMA', N'dbo',
'TABLE', N'Panel',
'COLUMN', N'Password_'
GO

EXEC sp_addextendedproperty
'MS_Description', N'Дата создания',
'SCHEMA', N'dbo',
'TABLE', N'Panel',
'COLUMN', N'CreateDate'
GO

EXEC sp_addextendedproperty
'MS_Description', N'1 - Объект отключен',
'SCHEMA', N'dbo',
'TABLE', N'Panel',
'COLUMN', N'Disabled'
GO

EXEC sp_addextendedproperty
'MS_Description', N'Тип сигнализации',
'SCHEMA', N'dbo',
'TABLE', N'Panel',
'COLUMN', N'Remarks'
GO

EXEC sp_addextendedproperty
'MS_Description', N'Имя компьютера, на котором изменялась данная запись последний раз',
'SCHEMA', N'dbo',
'TABLE', N'Panel',
'COLUMN', N'computer'
GO

EXEC sp_addextendedproperty
'MS_Description', N'Дата последнего изменения данной записи',
'SCHEMA', N'dbo',
'TABLE', N'Panel',
'COLUMN', N'DateLastChange'
GO

EXEC sp_addextendedproperty
'MS_Description', N'engineers.engineer_id',
'SCHEMA', N'dbo',
'TABLE', N'Panel',
'COLUMN', N'engineer_id'
GO

EXEC sp_addextendedproperty
'MS_Description', N'Areas.Area_id',
'SCHEMA', N'dbo',
'TABLE', N'Panel',
'COLUMN', N'Area_id'
GO

EXEC sp_addextendedproperty
'MS_Description', N'Дополнительная техническая информация',
'SCHEMA', N'dbo',
'TABLE', N'Panel',
'COLUMN', N'AdditionalTechnicalInformation'
GO

EXEC sp_addextendedproperty
'MS_Description', N'Приход теста от любого прибора считать тестированием всех приборов: 1 - да; 0 - нет',
'SCHEMA', N'dbo',
'TABLE', N'Panel',
'COLUMN', N'OneTestEqualAll'
GO

EXEC sp_addextendedproperty
'MS_Description', N'Masters.Master_id',
'SCHEMA', N'dbo',
'TABLE', N'Panel',
'COLUMN', N'master_id'
GO

EXEC sp_addextendedproperty
'MS_Description', N'Installers.Installer_id',
'SCHEMA', N'dbo',
'TABLE', N'Panel',
'COLUMN', N'installer_id'
GO

EXEC sp_addextendedproperty
'MS_Description', N'Имя компьютера, на котором данная запись редактируется в текущий момент',
'SCHEMA', N'dbo',
'TABLE', N'Panel',
'COLUMN', N'CompEditing'
GO

EXEC sp_addextendedproperty
'MS_Description', N'1 - Постоянный стенд',
'SCHEMA', N'dbo',
'TABLE', N'Panel',
'COLUMN', N'TestPanel'
GO

EXEC sp_addextendedproperty
'MS_Description', N'Частичные отключения',
'SCHEMA', N'dbo',
'TABLE', N'Panel',
'COLUMN', N'Partial'
GO

EXEC sp_addextendedproperty
'MS_Description', N'GPS координаты - Широта',
'SCHEMA', N'dbo',
'TABLE', N'Panel',
'COLUMN', N'Latitude'
GO

EXEC sp_addextendedproperty
'MS_Description', N'GPS координаты - Долгота',
'SCHEMA', N'dbo',
'TABLE', N'Panel',
'COLUMN', N'Longtitude'
GO

EXEC sp_addextendedproperty
'MS_Description', N'GPS координаты подтверждены',
'SCHEMA', N'dbo',
'TABLE', N'Panel',
'COLUMN', N'isGPSConfirm'
GO

EXEC sp_addextendedproperty
'MS_Description', N'Имя компьютера, на котором изменялась GPS координаты данной записи последний раз',
'SCHEMA', N'dbo',
'TABLE', N'Panel',
'COLUMN', N'CompLastEditGPS'
GO

EXEC sp_addextendedproperty
'MS_Description', N'Для подвижного объекта состояние включения зажигания: 1 - включено; 0 - выключено',
'SCHEMA', N'dbo',
'TABLE', N'Panel',
'COLUMN', N'Engine'
GO

EXEC sp_addextendedproperty
'MS_Description', N'vwPanelMobileGPS.TrackID',
'SCHEMA', N'dbo',
'TABLE', N'Panel',
'COLUMN', N'Track'
GO

EXEC sp_addextendedproperty
'MS_Description', N'Объект постоянно шлет GPS координаты: 1 - да; 0 - нет',
'SCHEMA', N'dbo',
'TABLE', N'Panel',
'COLUMN', N'isAlwaysSendGPS'
GO

EXEC sp_addextendedproperty
'MS_Description', N'1 - подвижный объект',
'SCHEMA', N'dbo',
'TABLE', N'Panel',
'COLUMN', N'Movable_Object'
GO

EXEC sp_addextendedproperty
'MS_Description', N'1 - пожарный объект',
'SCHEMA', N'dbo',
'TABLE', N'Panel',
'COLUMN', N'Panel_type'
GO

EXEC sp_addextendedproperty
'MS_Description', N'Pults.Pult_id',
'SCHEMA', N'dbo',
'TABLE', N'Panel',
'COLUMN', N'Pult_id'
GO

EXEC sp_addextendedproperty
'MS_Description', N'Имя пользователя, который изменял данную запись последний раз',
'SCHEMA', N'dbo',
'TABLE', N'Panel',
'COLUMN', N'UserName'
GO

EXEC sp_addextendedproperty
'MS_Description', N'RegionsTable.RegionID',
'SCHEMA', N'dbo',
'TABLE', N'Panel',
'COLUMN', N'RegionID'
GO

EXEC sp_addextendedproperty
'MS_Description', N'Объекты',
'SCHEMA', N'dbo',
'TABLE', N'Panel'
GO


-- ----------------------------
-- Auto increment value for Panel
-- ----------------------------
DBCC CHECKIDENT ('[dbo].[Panel]', RESEED, 46459)
GO


-- ----------------------------
-- Primary Key structure for table Panel
-- ----------------------------
ALTER TABLE [dbo].[Panel] ADD CONSTRAINT [pk_Panel] PRIMARY KEY CLUSTERED ([Panel_id])
WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON)  
ON [PRIMARY]
GO


-- ----------------------------
-- Foreign Keys structure for table Panel
-- ----------------------------
ALTER TABLE [dbo].[Panel] ADD CONSTRAINT [FK_Panel_Areas] FOREIGN KEY ([Area_id]) REFERENCES [dbo].[Areas] ([Area_id]) ON DELETE CASCADE ON UPDATE CASCADE
GO

ALTER TABLE [dbo].[Panel] ADD CONSTRAINT [FK_Panel_Installers] FOREIGN KEY ([installer_id]) REFERENCES [dbo].[Installers] ([Installer_id]) ON DELETE CASCADE ON UPDATE CASCADE
GO

ALTER TABLE [dbo].[Panel] ADD CONSTRAINT [FK_Panel_Masters] FOREIGN KEY ([master_id]) REFERENCES [dbo].[Masters] ([Master_id]) ON DELETE CASCADE ON UPDATE CASCADE
GO

