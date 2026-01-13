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

 Date: 03/08/2025 22:53:54
*/


-- ----------------------------
-- Table structure for Company
-- ----------------------------
IF EXISTS (SELECT * FROM sys.all_objects WHERE object_id = OBJECT_ID(N'[dbo].[Company]') AND type IN ('U'))
	DROP TABLE [dbo].[Company]
GO

CREATE TABLE [dbo].[Company] (
  [CompanyName] nvarchar(150) COLLATE Cyrillic_General_CI_AS  NULL,
  [address] nvarchar(150) COLLATE Cyrillic_General_CI_AS  NULL,
  [Telephones] nvarchar(100) COLLATE Cyrillic_General_CI_AS  NULL,
  [Director] nvarchar(150) COLLATE Cyrillic_General_CI_AS  NULL,
  [Director2] nvarchar(150) COLLATE Cyrillic_General_CI_AS  NULL,
  [Computer] nvarchar(100) COLLATE Cyrillic_General_CI_AS  NULL,
  [Memo] nvarchar(max) COLLATE Cyrillic_General_CI_AS  NULL,
  [LastEditDate] datetime  NULL,
  [UserName] nvarchar(200) COLLATE Cyrillic_General_CI_AS  NULL,
  [ServiceID] int  NULL,
  [CustomerID] int  NULL,
  [ID] int  IDENTITY(1,1) NOT FOR REPLICATION NOT NULL,
  [TypeID] int  NULL
)
GO

ALTER TABLE [dbo].[Company] SET (LOCK_ESCALATION = TABLE)
GO

EXEC sp_addextendedproperty
'MS_Description', N'Название',
'SCHEMA', N'dbo',
'TABLE', N'Company',
'COLUMN', N'CompanyName'
GO

EXEC sp_addextendedproperty
'MS_Description', N'Адрес',
'SCHEMA', N'dbo',
'TABLE', N'Company',
'COLUMN', N'address'
GO

EXEC sp_addextendedproperty
'MS_Description', N'Телефоны',
'SCHEMA', N'dbo',
'TABLE', N'Company',
'COLUMN', N'Telephones'
GO

EXEC sp_addextendedproperty
'MS_Description', N'Директор',
'SCHEMA', N'dbo',
'TABLE', N'Company',
'COLUMN', N'Director'
GO

EXEC sp_addextendedproperty
'MS_Description', N'Ответственный',
'SCHEMA', N'dbo',
'TABLE', N'Company',
'COLUMN', N'Director2'
GO

EXEC sp_addextendedproperty
'MS_Description', N'Имя компьютера, на котором изменялась данная запись последний раз',
'SCHEMA', N'dbo',
'TABLE', N'Company',
'COLUMN', N'Computer'
GO

EXEC sp_addextendedproperty
'MS_Description', N'Дополнительная информация',
'SCHEMA', N'dbo',
'TABLE', N'Company',
'COLUMN', N'Memo'
GO

EXEC sp_addextendedproperty
'MS_Description', N'Дата последнего изменения записи',
'SCHEMA', N'dbo',
'TABLE', N'Company',
'COLUMN', N'LastEditDate'
GO

EXEC sp_addextendedproperty
'MS_Description', N'Имя пользователя, который изменял данную запись последний раз',
'SCHEMA', N'dbo',
'TABLE', N'Company',
'COLUMN', N'UserName'
GO

EXEC sp_addextendedproperty
'MS_Description', N'ServiceOrganization.ID',
'SCHEMA', N'dbo',
'TABLE', N'Company',
'COLUMN', N'ServiceID'
GO

EXEC sp_addextendedproperty
'MS_Description', N'Customers.ID',
'SCHEMA', N'dbo',
'TABLE', N'Company',
'COLUMN', N'CustomerID'
GO

EXEC sp_addextendedproperty
'MS_Description', N'Плательщик',
'SCHEMA', N'dbo',
'TABLE', N'Company'
GO


-- ----------------------------
-- Auto increment value for Company
-- ----------------------------
DBCC CHECKIDENT ('[dbo].[Company]', RESEED, 46555)
GO


-- ----------------------------
-- Primary Key structure for table Company
-- ----------------------------
ALTER TABLE [dbo].[Company] ADD CONSTRAINT [pk_Company] PRIMARY KEY CLUSTERED ([ID])
WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON)  
ON [PRIMARY]
GO


-- ----------------------------
-- Foreign Keys structure for table Company
-- ----------------------------
ALTER TABLE [dbo].[Company] ADD CONSTRAINT [FK_Company_ServiceOrganization] FOREIGN KEY ([ServiceID]) REFERENCES [dbo].[ServiceOrganization] ([ID]) ON DELETE NO ACTION ON UPDATE CASCADE
GO

ALTER TABLE [dbo].[Company] ADD CONSTRAINT [FK_Company_Customers] FOREIGN KEY ([CustomerID]) REFERENCES [dbo].[Customers] ([ID]) ON DELETE NO ACTION ON UPDATE CASCADE
GO

ALTER TABLE [dbo].[Company] ADD CONSTRAINT [FK_Company_CompanyType] FOREIGN KEY ([TypeID]) REFERENCES [dbo].[CompanyType] ([ID]) ON DELETE SET NULL ON UPDATE CASCADE
GO

