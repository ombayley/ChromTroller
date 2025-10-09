.dx files have been introduced in the latest version of Agilent's OpenLab CDS software and have no official documentation fo rhtier build.
These files are compressed archives and can be extracted with pythons zipfile module.
within these files are:
```
MSData/MSScan.xsd
_rels/.rels
[Content_Types].xml
MSData/Contents.xml
MSData/Devices.xml
2d4ed283-e283-470a-985f-c8650b5b92ba.UV
2d4ed283-e283-470a-985f-c8650b5b92ba.UVD
_rels/2d4ed283-e283-470a-985f-c8650b5b92ba.UV.rels
1aff4f0e-4b5d-4e62-a6b1-08e206e7c1a8.IT
...
4bf708a6-c0b3-4d70-87d3-de375632a9f9.IT
a94b341b-8600-47a2-aad6-641f0e04fb1f.CH
742c0a8e-994d-4588-a6a1-122438f1cbba.grd
2ce53aef-85cd-485f-84b8-cc1849d7ffb5.grd
MSData/MSTS.xml
injection.acmd

```

the .xml and .xsd files contain metdatadata on the aquired MS data which is stored seperately in the .MSPeak.bin and .MSScan.bin files.
the .UV files contain the 3D UV data of the chromatogram across wavelengths.
the .UVD files contain UV data of the chromatogram at a given wavelength.
the .IT files contain all the info of the hardware (temperatures, currents, pressures, etc...) but are not marked 
