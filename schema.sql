-- Copyright 2009 FriendFeed
--
-- Licensed under the Apache License, Version 2.0 (the "License"); you may
-- not use this file except in compliance with the License. You may obtain
-- a copy of the License at
--
--     http://www.apache.org/licenses/LICENSE-2.0
--
-- Unless required by applicable law or agreed to in writing, software
-- distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
-- WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
-- License for the specific language governing permissions and limitations
-- under the License.

-- To create the database:
--   CREATE DATABASE blog;
--   GRANT ALL PRIVILEGES ON blog.* TO 'blog'@'localhost' IDENTIFIED BY 'blog';
--
-- To reload the tables:
--   mysql --user=blog --password=blog --database=blog < schema.sql

SET SESSION storage_engine = "InnoDB";
SET SESSION time_zone = "+8:00";
ALTER DATABASE CHARACTER SET "utf8";

DROP TABLE IF EXISTS entries;
CREATE TABLE entries (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    author_id INT NOT NULL REFERENCES authors(id),
    slug VARCHAR(100) NOT NULL UNIQUE,
    title VARCHAR(512) NOT NULL,
    markdown MEDIUMTEXT NOT NULL,
    html MEDIUMTEXT NOT NULL,
    published DATETIME NOT NULL,
    updated TIMESTAMP NOT NULL,
    KEY (published)
);

DROP TABLE IF EXISTS authors;
CREATE TABLE authors (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(100) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    hashed_password VARCHAR(100) NOT NULL
);

--去除重复数据 business_base
DELETE FROM business_base
WHERE
    business_id IN (SELECT
        id
    FROM
        (SELECT
            a.business_id as id
        FROM
            business_base a
        GROUP BY a.business_id
        HAVING COUNT(*) = 2) AS t1)
    AND id NOT IN (SELECT
        id
    FROM
        (SELECT
            MIN(id) as id
        FROM
            business_base a
        GROUP BY a.business_id
        HAVING COUNT(business_id) = 2) AS t2);
--去除重复数据 business_base_info
DELETE FROM business_base_info
WHERE
    business_id IN (SELECT
        id
    FROM
        (SELECT
            a.business_id as id
        FROM
            business_base_info a
        GROUP BY a.business_id
        HAVING COUNT(*) = 2) AS t1)
    AND id NOT IN (SELECT
        id
    FROM
        (SELECT
            MIN(id) as id
        FROM
            business_base_info a
        GROUP BY a.business_id
        HAVING COUNT(business_id) = 2) AS t2);
#pf_base加入索引
ALTER TABLE `bigdata`.`pf_base`
DROP INDEX `idx_base_regprocityno` ,
ADD INDEX `idx_base_regprocityno` (`registerProvince` ASC, `registerCity` ASC, `registerNo` ASC);
#获取区坐标
select concat('\'',aaa.city,'\':[',aaa.reg_b,',',aaa.reg_a,'],') from (
select city,avg(reg_a) as reg_a,avg(reg_b) as reg_b from (
select a.registerCity as city,avg(substring_index(regCoordinate,',','1')) as reg_a ,avg(substring_index(regCoordinate,',','-1')) as reg_b  FROM
    bigdata.pf_base a group by a.registerCity
union
select a.officeCity as city,avg(substring_index(officeCoordinate,',','1')) as reg_a ,avg(substring_index(officeCoordinate,',','-1')) as reg_b  FROM
    bigdata.pf_base a group by a.officeCity) as aa where aa.city<>'' group by city) as aaa;
#获取公司异地办公情况
SELECT
    CONCAT('[{name:\'',
            a.registerCity,
            '\',value:',COUNT(a.registerCity),'}, {name:\'',
            a.officeCity,
            '\'',
            '}],') AS vcount
FROM
    bigdata.pf_base a
WHERE
    a.registerCity <> a.officeCity
        AND a.registerCity <> ''
        AND officeCity <> ''
GROUP BY a.registerCity , a.officeCity;
