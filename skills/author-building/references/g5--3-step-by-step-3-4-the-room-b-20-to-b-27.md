<!-- chunk: g5--3-step-by-step-3-4-the-room-b-20-to-b-27 | source: 05-worked-example.md | title: 3. Step by step: 3.4 The room (B-20 to B-27) | rules: - -->
### 3.4 The room (B-20 to B-27)

```
#700273=IFCSPACE('1C1BaaS91KOgLuDEt1VXqX',$,'Example work room',$,$,#700270,#700272,'Example work room',.ELEMENT.,.INTERNAL.,0.);
#700274=IFCRELAGGREGATES('3jyuNv4XzQSRLalH7sDq_3',$,$,$,#700034,(#700273));
#700275=IFCPROPERTYSINGLEVALUE('RoomId',$,IFCTEXT('EX-001'),$);
#700276=IFCPROPERTYSINGLEVALUE('Occupant',$,IFCTEXT('Example Occupant'),$);
#700277=IFCPROPERTYSINGLEVALUE('Function',$,IFCTEXT('Work room'),$);
```

The room is an `IfcSpace` (the IFC name for a room or zone) aggregated under the level. Its geometry is an extrusion of the 4.8 by
3.8 floor outline up to 3.0 m. The properties are single values in a property set linked by `IfcRelDefinesByProperties`. `RoomId` is
`EX-001`, six characters. The room table row repeats them, and the net area 18.24 m2 equals 4.8 times 3.8.
