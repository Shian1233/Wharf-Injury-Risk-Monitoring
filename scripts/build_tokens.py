"""Export supplied SCSS design tokens to browser CSS without a frontend build dependency."""
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[1]
tokens=ROOT/'reference/design/design-token/css'
palette=(tokens/'palette.scss').read_text(encoding='utf-8')
variables=dict(re.findall(r'\$([\w-]+):\s*([^;]+);',palette))
def replace(match):
    expression=match[1]
    if expression.startswith('$'): return variables.get(expression[1:],'initial')
    m=re.fullmatch(r'rgba\(\$([\w-]+),\s*([\d.]+)\)',expression)
    if m:
        color=variables[m[1]]; return 'rgba('+','.join(str(int(color[i:i+2],16)) for i in [1,3,5])+','+m[2]+')'
    return 'initial'
out=['/* Derived from supplied design specification v1.1.0.1; source preserved in reference/design. */',':root{']
for file in ['palette.scss','semantic.scss','spacing.scss','animation.scss']:
    text=(tokens/file).read_text(encoding='utf-8')
    for key,val in re.findall(r'(--iflyv-[\w-]+):\s*([^;]+);',text):
        value=re.sub(r'#\{([^}]+)\}',replace,val)
        out.append(key+':'+value+';')
font=(tokens/'font.scss').read_text(encoding='utf-8')
font_vars=dict(re.findall(r'\$([\w-]+):\s*([^;]+);',font))
font_vars['font-family-emphasis']='PuHui, '+font_vars['font-family-base']
font_vars['font-family-base']='-apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", "PingFang SC", "Noto Sans SC", sans-serif'
font_vars['font-family-emphasis']='PuHui, '+font_vars['font-family-base']
for key,val in re.findall(r'(--iflyv-[\w-]+):\s*([^;]+);',font):
    value=re.sub(r'#\{\$([\w-]+)\}',lambda m:font_vars[m[1]],val)
    out.append(key+':'+value.strip()+';')
out+=['}']
(ROOT/'frontend/vendor/tokens.css').write_text('\n'.join(out),encoding='utf-8')
print('Design tokens exported')
