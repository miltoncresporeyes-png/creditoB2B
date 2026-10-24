const M=require('./assets/model.js');
global.CreditModel=M;
const ML=require('./assets/ml.js');
global.CreditML=ML;

const ex={
  razonSocial:'Andes Tecnología SpA',rut:'76.543.210-3',rutERut:'76.543.210-3',rutSolicitante:'12.345.678-5',
  representantes:'12.345.678-5',sector:'servicios_ti',antiguedad:8,ventas12m:1200000000,montoSolicitado:50000000,
  plazo:'60',exposicionActual:12000000,concentracionTopCliente:25,activoCorriente:320000000,pasivoCorriente:180000000,
  inventarios:30000000,caja:40000000,cuentasPorCobrar:180000000,ebitda:150000000,flujoCajaOperacional:110000000,
  gastosFinancieros:18000000,servicioDeuda:35000000,pasivoTotal:380000000,patrimonio:300000000,deudaFinanciera:120000000,
  deudaFinancieraCP:30000000,maxDiasMora:0,deudaVencida:0,deudaCastigada:0,instituciones:2,protestos:0,morosidades:0,
  montoMorosidades:0,pagoHistorico:'puntual',facturasVencidas:0,situacionTributaria:'ok',deudaTGR:0,f29SinDeclarar:0,
  tendenciaVentas:'sube',docs:{trib:true,erut:true,cmf:true,escritura:true,eecc:true,dicom:true},inicioVigente:true,
  sociedadVigente:true,facultades:true,eeccVerificados:true,aval:false,garantia:false,seguroCredito:true,
  limitePoliticaRiesgo:80000000,factorComercial:0.9,multiplicadorFlujo:1,validacionLegal:true,autorizacion90:false,
  justificacion90:false
};
const r=M.evaluate(ex);
console.log('example status:',r.status.key,'score:',r.score,'prediction:',r.prediction.label);
if (r.status.key!=='approved') { console.error('FAIL: expected approved'); process.exit(1); }
if (!r.prediction || !r.prediction.label) { console.error('FAIL: prediction missing'); process.exit(1); }
console.log('OK');