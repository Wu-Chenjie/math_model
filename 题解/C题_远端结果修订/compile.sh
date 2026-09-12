#!/bin/sh
set -eu
cd "$(dirname "$0")"
/Library/TeX/texbin/xelatex -interaction=nonstopmode -halt-on-error revised-main.tex
/Library/TeX/texbin/xelatex -interaction=nonstopmode -halt-on-error revised-main.tex
cp revised-main.pdf output/pdf/基于固定时域与预报融合的微网跨日随机调度.pdf
