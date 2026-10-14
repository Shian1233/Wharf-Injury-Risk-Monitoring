const fs=require('fs');
const echarts=require('../frontend/vendor/echarts.min.js');
const specs=JSON.parse(fs.readFileSync(0,'utf8'));
process.stdout.write(JSON.stringify(specs.map(spec=>{
  const chart=echarts.init(null,null,{renderer:'svg',ssr:true,width:900,height:spec.height||400});
  try{chart.setOption(spec.option);return chart.renderToSVGString()}finally{chart.dispose()}
})));
