SELECT 
  a.TestTime,
  a.UUID,
  a.Direction,
  a.MeanThroughputMbps,
  a.MinRTT,
  a.LossRate,
  client.Geo.Subdivision1Name,
  client.Geo.Latitude,
  client.Geo.Longitude,
  client.Geo.AccuracyRadiusKm,
  client.Geo.City,
  client.Network.ASName,
  client.Network.ASNumber
FROM `measurement-lab.ndt.unified_downloads`
WHERE date >= '2021-12-31' AND date <= '2022-01-02'
  AND client.Geo.CountryCode = 'TW'
  AND client.Geo.Subdivision1Name = 'Taipei City'
  AND (
    client.Network.ASName = 'Taiwan Mobile Co., Ltd.' OR
    client.Network.ASName = 'Far EastTone Telecommunication Co., Ltd.' OR
    client.Network.ASName = 'Mobile Business Group' OR
    client.Network.ASName LIKE '%Taiwan Star Telecom%'
  )
ORDER BY a.TestTime DESC