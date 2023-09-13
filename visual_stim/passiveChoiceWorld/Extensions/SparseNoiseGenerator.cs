using Bonsai;
using System;
using System.ComponentModel;
using System.Collections.Generic;
using System.Linq;
using System.Reactive.Linq;
using System.Reactive;
using System.Reactive.Disposables;
using MathNet.Numerics.Distributions;
using MathNet.Numerics;

[Combinator]
[Description("Generates a non-overlapping distribution of values in a grid.")]
[WorkflowElementCategory(ElementCategory.Transform)]
public class SparseNoiseGenerator
{

    public SparseNoiseGenerator() {

    }

    [Description("The number of rows in the sparse noise grid.")]
    public int Rows { get; set; }

    [Description("The number of columns in the sparse noise grid.")]
    public int Columns { get; set; }

    [Description("The duration (seconds) for all stimuli.")]
    public float Duration { get; set; }

    [Description("The Poisson rate (Hz) for all stimuli.")]
    public float Rate { get; set; }

    public IObservable<byte[]> Process(IObservable<double> source, IObservable<Random> randomSource)
    {
        return Observable.Defer(() =>
        {
            double[] nextUpdate = null;
            byte[] state = null;
            return source.CombineLatest(
                randomSource,
                (elapsedTime, random) =>
                {
                    // setup the persistent arrays
                    if (nextUpdate == null)
                    {
                        state = Enumerable.Repeat<byte>(128, Rows * Columns).ToArray();
                        nextUpdate = new double[Rows * Columns];
                        for (int i = 0; i < nextUpdate.Length; i++)
                        {
                            // sample when the next poisson event will happen for each square using rate
                            nextUpdate[i] = Exponential.Sample(random, Rate);
                        }                        
                    }

                    // check each visual angle quad for state and update
                    for (int i = 0; i < state.Length; i++)
                    {
                        nextUpdate[i] -= elapsedTime;
                        if (nextUpdate[i] <= 0)
                        {
                            // if neutral gray, flip the quad to black or white
                            if (state[i] == 128)
                            {
                                state[i] = (byte)(DiscreteUniform.Sample(random, 0, 1) * byte.MaxValue);
                                nextUpdate[i] = Duration;
                            }
                            else // if active, go back to neutral and sample next poisson interval using rate
                            {
                                state[i] = 128;
                                nextUpdate[i] = Exponential.Sample(random, Rate);
                            }
                        }
                   }

                    // Combinatorics.SelectPermutationInplace(result, distribution.RandomSource);
                    return state;
                }
            );

        });
    }
}
