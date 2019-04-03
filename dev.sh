#!/bin/bash
rm -f .testmondata
ptw -cwq -- --testmon --quiet --tb=short
