-- 查詢跨年前 2,3,4 週與後 1,2,3 週的手機測試數據 (作為 baseline)
-- (需更改日期以分別搜尋前與後的資料)

DECLARE year STRING;
SET year = '2026'; 

SELECT 
  -- 1. 時間與年度基礎資訊
  a.TestTime,
  EXTRACT(YEAR FROM DATETIME(a.TestTime, 'Asia/Taipei')) AS DataYear,
  FORMAT_DATETIME('%H:%M:%S', DATETIME(a.TestTime, 'Asia/Taipei')) AS LocalTime,
  
  -- 2. 網路效能核心欄位
  a.UUID,
  a.Direction,
  a.MeanThroughputMbps,
  a.MinRTT,
  a.LossRate,
  
  -- 3. 空間地理標籤
  client.Geo.Subdivision1Name,
  client.Geo.City,
  client.Geo.Latitude,
  client.Geo.Longitude,
  client.Geo.AccuracyRadiusKm,
  
  -- 4. 電信商欄位
  client.Network.ASName,
  client.Network.ASNumber
FROM `measurement-lab.ndt.unified_downloads`
WHERE 
  date IN (
    CAST(year || '-01-07' AS DATE), CAST(year || '-01-08' AS DATE),  
    CAST(year || '-01-14' AS DATE), CAST(year || '-01-15' AS DATE),  
    CAST(year || '-01-21' AS DATE), CAST(year || '-01-22' AS DATE),  
    CAST(year || '-01-28' AS DATE), CAST(year || '-01-29' AS DATE)   
  )
  AND client.Geo.CountryCode = 'TW'
  AND client.Geo.Subdivision1Name = 'Taipei City'
  
  AND (
    client.Network.ASName LIKE '%Taiwan Mobile%' 
    OR client.Network.ASName LIKE '%Far EastTone%' 
    OR client.Network.ASName LIKE '%Mobile Business Group%' 
    OR client.Network.ASName LIKE '%Taiwan Star%'
  )
  
  -- 【時區精確對齊】強制轉換為台北時間
  AND (
    -- 當天 12:00 ~ 23:59
    (CAST(EXTRACT(DATE FROM DATETIME(a.TestTime, 'Asia/Taipei')) AS STRING) IN (year || '-01-07', year || '-01-14', year || '-01-21', year || '-01-28')
     AND EXTRACT(HOUR FROM DATETIME(a.TestTime, 'Asia/Taipei')) BETWEEN 12 AND 23)
    OR
    -- 隔天 00:00 ~ 12:00
    (CAST(EXTRACT(DATE FROM DATETIME(a.TestTime, 'Asia/Taipei')) AS STRING) IN (year || '-01-08', year || '-01-15', year || '-01-22', year || '-01-29')
     AND EXTRACT(HOUR FROM DATETIME(a.TestTime, 'Asia/Taipei')) BETWEEN 0 AND 11) 
  )
ORDER BY a.TestTime DESC;